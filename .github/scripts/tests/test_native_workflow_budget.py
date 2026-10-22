"""The hosted job must outlive its unchanged native-service budget."""
from pathlib import Path
import re
import unittest


class NativeWorkflowBudgetTests(unittest.TestCase):
    def test_browser_jobs_use_the_exact_qualified_python_release(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/native-browser.yml").read_text()
        self.assertEqual(
            re.findall(r"^          python-version: '([^']+)'$", workflow, re.MULTILINE),
            ["3.12.3"],
        )

    def test_browser_jobs_install_the_existing_hashed_application_closure(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/native-browser.yml").read_text()
        install = workflow.split("      - name: Install app dependencies\n", 1)[1].split("      - name:", 1)[0]
        self.assertIn("bash .github/scripts/install-ci-app-runtime.sh", install)
        self.assertIn("npm --prefix frontend ci", install)
        self.assertNotIn("pip install -r backend/requirements.txt", install)

    def test_job_reserves_setup_and_cleanup_outside_the_native_service(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/native-browser.yml").read_text()
        launcher = (root / ".github/scripts/run-native-browser-ci.sh").read_text()
        jobs = re.findall(r"^    timeout-minutes: (\d+)$", workflow, re.MULTILINE)
        self.assertEqual(jobs, ["60"])
        self.assertIn("--property=RuntimeMaxSec=2700s", launcher)
        self.assertIn("--property=TimeoutStopSec=15s", launcher)
        self.assertEqual(int(jobs[0]) * 60 - 2700, 900)


class VendorInstallContracts(unittest.TestCase):
    """Execute only an inert shell protocol; never install or contact a vendor."""

    MOCKS = r'''
record() { printf '%s\n' "$*" >> "$CALLS"; }
test() {
  record test "$@"
  case "$*" in '! -L /opt'|'! -L /opt/google'|'! -L /opt/google/chrome') return 0 ;; esac
  return 97
}
sudo() {
  record sudo "$@"
  if [[ "$1" == -n ]]; then shift; fi
  case "$1" in
    tee) /bin/cat >/dev/null ;;
    install|curl) ;;
    apt-get) shift; apt-get "$@" ;;
    /usr/bin/timeout)
      [[ "$2" == --signal=TERM && "$3" == --kill-after=15s &&
         ( "$4" == 120s || "$4" == 300s ) && "$5" == apt-get ]] || return 95
      shift 5
      # Exercise the real process-group timeout with only an owned fake command.
      /usr/bin/timeout --signal=TERM --kill-after=0.2s 0.2s \
        /usr/bin/bash --noprofile --norc "$RUNNER_TEMP/fake-apt" "$@"
      ;;
    *) return 98 ;;
  esac
}
curl() {
  record curl "$@"
  if [[ "$1" == --connect-timeout ]]; then
    [[ "$2" == 10 && "$3" == --max-time && "$4" == 90 ]] || return 99
    shift 4
  fi
  [[ "$1" == -fsSLo && "$2" == "$RUNNER_TEMP/google-linux-key.pub" && "$3" == https://dl.google.com/linux/linux_signing_key.pub ]] || return 99
  ((CURL_STATUS == 0)) || return "$CURL_STATUS"
  printf 'PUBLIC-FAKE-KEY\n' > "$2"
}
gpg() {
  record gpg "$@"
  if [[ "$*" == --batch\ --show-keys\ --with-colons\ * ]]; then
    printf 'fpr:::::::::%s:\n' "$FINGERPRINT"
  elif [[ "$*" == '--batch --dearmor' ]]; then
    /bin/cat
  else return 96
  fi
}
apt-get() { /usr/bin/bash --noprofile --norc "$RUNNER_TEMP/fake-apt" "$@"; }
source "$HELPER" "$@"
'''

    FAKE_APT = r'''
printf 'apt-get %s\n' "$*" >> "$CALLS"
stage=install
[[ " $* " != *' update '* ]] || stage=update
if [[ "$stage" == "$STALL_STAGE" ]]; then
  trap '' TERM
  printf '%s\n' "$BASHPID" > "$RUNNER_TEMP/command.pid"
  /usr/bin/bash --noprofile --norc -c '
    trap "" TERM
    printf "%s\n" "$BASHPID" > "$RUNNER_TEMP/descendant.pid"
    while :; do /bin/sleep 0.05; done
  ' &
  wait
fi
if [[ "$stage" == update ]]; then exit "$UPDATE_STATUS"; fi
exit "$INSTALL_STATUS"
'''

    def run_helper(self, *args, fingerprint='EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796',
                   update_status=0, install_status=0, curl_status=0, stall_stage=''):
        import os
        import signal
        import subprocess
        import tempfile

        root = Path(__file__).resolve().parents[3]
        helper = root / '.github/scripts/install-ci-vendor-browser.sh'
        self.assertTrue(helper.is_file(), 'Shared signed-vendor installer is missing')
        with tempfile.TemporaryDirectory(prefix='mtg-inert-vendor-') as temporary:
            scratch = Path(temporary)
            calls = scratch / 'calls'
            (scratch / 'fake-apt').write_text(self.FAKE_APT)
            process = subprocess.Popen(['/usr/bin/bash', '--noprofile', '--norc', '-c',
                                     self.MOCKS, 'inert-vendor', *args],
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': temporary,
                     'RUNNER_TEMP': temporary, 'CALLS': str(calls), 'HELPER': str(helper),
                     'FINGERPRINT': fingerprint, 'UPDATE_STATUS': str(update_status),
                     'INSTALL_STATUS': str(install_status), 'CURL_STATUS': str(curl_status),
                     'STALL_STAGE': stall_stage}, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=5)
                result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
                if stall_stage:
                    for name in ('command', 'descendant'):
                        pidfile = scratch / (name + '.pid')
                        self.assertTrue(pidfile.is_file(), name + ' was not exercised')
                        state = Path('/proc') / pidfile.read_text().strip() / 'stat'
                        self.assertTrue(not state.exists() or state.read_text().split(') ', 1)[1][0] == 'Z',
                                        name + ' survived the timeout')
            except subprocess.TimeoutExpired:
                self.fail('Installer exceeded the inert five-second deadline')
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate(timeout=5)
            lines = calls.read_text().splitlines() if calls.exists() else []
            return result, [line.replace(temporary, '<OWN>') for line in lines]

    def test_actual_helper_preserves_both_official_repository_and_directory_protocols(self):
        for vendor in ('chrome', 'brave'):
            with self.subTest(vendor=vendor):
                result, calls = self.run_helper(vendor)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, '')
                self.assertEqual(calls[0:2], ['test ! -L /opt',
                    'sudo -n install -d -o root -g root -m 0755 /opt'])
                apt = [line for line in calls if line.startswith('apt-get ')]
                self.assertEqual(len(apt), 2)
                self.assertTrue(apt[0].endswith(' update'))
                self.assertIn(' install -y ', apt[1])
                if vendor == 'chrome':
                    self.assertIn('test ! -L /opt/google', calls)
                    self.assertIn('test ! -L /opt/google/chrome', calls)
                    self.assertIn('sudo -n install -d -o root -g root -m 0755 /opt/google /opt/google/chrome', calls)
                    self.assertIn('curl --connect-timeout 10 --max-time 90 -fsSLo <OWN>/google-linux-key.pub https://dl.google.com/linux/linux_signing_key.pub', calls)
                    self.assertIn('gpg --batch --show-keys --with-colons <OWN>/google-linux-key.pub', calls)
                    self.assertIn('sudo -n tee /usr/share/keyrings/mtg-google-chrome.gpg', calls)
                    self.assertIn('sudo -n tee /etc/apt/sources.list.d/mtg-google-chrome.list', calls)
                    self.assertTrue(apt[1].endswith(' install -y --reinstall google-chrome-stable'))
                else:
                    self.assertIn('sudo -n curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg', calls)
                    self.assertIn('sudo -n curl -fsSLo /etc/apt/sources.list.d/brave-browser-release.sources https://brave-browser-apt-release.s3.brave.com/brave-browser.sources', calls)

    def test_google_update_is_scoped_preserves_lists_and_install_dependency_scope(self):
        result, calls = self.run_helper('chrome')
        self.assertEqual(result.returncode, 0, result.stderr)
        update, install = [line for line in calls if line.startswith('apt-get ')]
        for option in ('Dir::Etc::sourcelist=/etc/apt/sources.list.d/mtg-google-chrome.list',
                       'Dir::Etc::sourceparts=-', 'APT::Get::List-Cleanup=0',
                       'APT::Update::Error-Mode=any'):
            self.assertIn('-o ' + option, update)
            self.assertNotIn(option.split('=')[0], install)
        for command in (update, install):
            for option in ('Acquire::http::Timeout=30', 'Acquire::https::Timeout=30',
                           'Acquire::Retries=1'):
                self.assertIn('-o ' + option, command)
        for duration, command in (('120s', update), ('300s', install)):
            self.assertIn('sudo -n /usr/bin/timeout --signal=TERM --kill-after=15s ' +
                          duration + ' ' + command, calls)

    def test_google_fetch_update_and_install_fail_closed_without_fallback(self):
        for kwargs, status, count in (({'curl_status': 28}, 28, 0),
                                      ({'update_status': 100}, 100, 1),
                                      ({'install_status': 100}, 100, 2)):
            with self.subTest(**kwargs):
                result, calls = self.run_helper('chrome', **kwargs)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(sum(line.startswith('apt-get ') for line in calls), count)
                self.assertLessEqual(sum(line.endswith(' update') for line in calls
                                         if line.startswith('apt-get ')), 1)

    def test_google_stalled_update_and_install_kill_command_and_descendant(self):
        for stage, count in (('update', 1), ('install', 2)):
            with self.subTest(stage=stage):
                result, calls = self.run_helper('chrome', stall_stage=stage)
                self.assertIn(result.returncode, (124, 137))
                self.assertEqual(sum(line.startswith('apt-get ') for line in calls), count)

    def test_google_repository_trust_and_no_broad_fallback_are_preserved(self):
        root = Path(__file__).resolve().parents[3]
        source = (root / '.github/scripts/install-ci-vendor-browser.sh').read_text()
        chrome = source.split('if [[ "$MTG_BROWSER_VENDOR" == chrome ]]; then', 2)[2].split('\nelse\n', 1)[0]
        self.assertIn('deb [arch=amd64 signed-by=/usr/share/keyrings/mtg-google-chrome.gpg,EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796] https://dl.google.com/linux/chrome/deb/ stable main', chrome)
        self.assertIn("grep '^fpr:::::::::EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796:'", chrome)
        for forbidden in ('trusted=yes', '--allow-unauthenticated', 'AllowInsecureRepositories',
                          'AllowDowngradeToInsecureRepositories', '--fix-missing', '|| true',
                          'azure.archive', 'archive.ubuntu', 'sources.list.d/ubuntu'):
            self.assertNotIn(forbidden, chrome)

    def test_unknown_arguments_and_wrong_google_fingerprint_cannot_install(self):
        for args in ((), ('chromium',), ('chrome', 'extra'), ('chrome\ninjected',)):
            with self.subTest(args=args):
                result, calls = self.run_helper(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])
                self.assertEqual(result.stdout + result.stderr, '')
        result, calls = self.run_helper('chrome', fingerprint='UNTRUSTED')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('apt-get' in line or ' tee ' in line for line in calls))

    def test_native_and_ordinary_workflows_share_installer_and_bind_current_chrome(self):
        root = Path(__file__).resolve().parents[3]
        native = (root / '.github/workflows/native-browser.yml').read_text()
        browser = (root / '.github/workflows/ci.yml').read_text().split('\n  browser:\n', 1)[1]
        self.assertIn('bash .github/scripts/install-ci-vendor-browser.sh "$MTG_BROWSER_VENDOR"', native)
        self.assertIn('      - .github/scripts/install-ci-vendor-browser.sh\n', native)
        self.assertNotIn('https://dl.google.com/linux/chrome/deb/', native)
        self.assertNotIn('https://brave-browser-apt-release.s3.brave.com/', native)
        self.assertIn('bash .github/scripts/install-ci-vendor-browser.sh chrome', browser)
        self.assertIn('/opt/google/chrome/chrome --version', browser)
        self.assertLess(browser.index('install-ci-vendor-browser.sh chrome'),
                        browser.index('Browser action and recovery flows'))
        self.assertIn('MTG_CHROME: /opt/google/chrome/chrome', browser)
        self.assertIn("MTG_BROWSER_NO_SANDBOX: '1'", browser)
        self.assertIn('run: bash frontend/tests/run-browser-ci.sh', browser)
        self.assertIn("MTG_BROWSER_NO_SANDBOX: '0'", native)

    def test_ci_concurrency_cancels_only_superseded_active_pull_requests(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / '.github/workflows/ci.yml').read_text()
        self.assertIn(
            "\nconcurrency:\n"
            "  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}\n"
            "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n",
            workflow,
        )
        self.assertEqual(len(re.findall(r'^concurrency:$', workflow, re.MULTILINE)), 1)
        self.assertNotIn('cancel-in-progress: true', workflow)


if __name__ == "__main__":
    unittest.main()
