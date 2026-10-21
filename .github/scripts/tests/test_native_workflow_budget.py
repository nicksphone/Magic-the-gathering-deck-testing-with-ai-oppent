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
  case "$1" in
    tee) /bin/cat >/dev/null ;;
    install|curl|apt-get) ;;
    *) return 98 ;;
  esac
}
curl() {
  record curl "$@"
  [[ "$1" == -fsSLo && "$2" == "$RUNNER_TEMP/google-linux-key.pub" && "$3" == https://dl.google.com/linux/linux_signing_key.pub ]] || return 99
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
source "$HELPER" "$@"
'''

    def run_helper(self, *args, fingerprint='EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796'):
        import subprocess
        import tempfile

        root = Path(__file__).resolve().parents[3]
        helper = root / '.github/scripts/install-ci-vendor-browser.sh'
        self.assertTrue(helper.is_file(), 'Shared signed-vendor installer is missing')
        with tempfile.TemporaryDirectory(prefix='mtg-inert-vendor-') as temporary:
            scratch = Path(temporary)
            calls = scratch / 'calls'
            result = subprocess.run(['/usr/bin/bash', '--noprofile', '--norc', '-c',
                                     self.MOCKS, 'inert-vendor', *args],
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': temporary,
                     'RUNNER_TEMP': temporary, 'CALLS': str(calls), 'HELPER': str(helper),
                     'FINGERPRINT': fingerprint}, capture_output=True, text=True, timeout=5)
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
                    'sudo install -d -o root -g root -m 0755 /opt'])
                self.assertEqual(calls.count('sudo apt-get update'), 1)
                install = ('sudo apt-get install -y --reinstall google-chrome-stable'
                           if vendor == 'chrome' else 'sudo apt-get install -y brave-browser')
                self.assertEqual(calls.count(install), 1)
                self.assertLess(calls.index('sudo apt-get update'), calls.index(install))
                if vendor == 'chrome':
                    self.assertIn('test ! -L /opt/google', calls)
                    self.assertIn('test ! -L /opt/google/chrome', calls)
                    self.assertIn('sudo install -d -o root -g root -m 0755 /opt/google /opt/google/chrome', calls)
                    self.assertIn('curl -fsSLo <OWN>/google-linux-key.pub https://dl.google.com/linux/linux_signing_key.pub', calls)
                    self.assertIn('gpg --batch --show-keys --with-colons <OWN>/google-linux-key.pub', calls)
                    self.assertIn('sudo tee /usr/share/keyrings/mtg-google-chrome.gpg', calls)
                    self.assertIn('sudo tee /etc/apt/sources.list.d/mtg-google-chrome.list', calls)
                else:
                    self.assertIn('sudo curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg', calls)
                    self.assertIn('sudo curl -fsSLo /etc/apt/sources.list.d/brave-browser-release.sources https://brave-browser-apt-release.s3.brave.com/brave-browser.sources', calls)

    def test_unknown_arguments_and_wrong_google_fingerprint_cannot_install(self):
        for args in ((), ('chromium',), ('chrome', 'extra'), ('chrome\ninjected',)):
            with self.subTest(args=args):
                result, calls = self.run_helper(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])
                self.assertEqual(result.stdout + result.stderr, '')
        result, calls = self.run_helper('chrome', fingerprint='UNTRUSTED')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('apt-get' in line or 'sudo tee ' in line for line in calls))

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
