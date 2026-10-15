# Native Vendor Browser CI

The separate `Native Linux Browsers` workflow runs the existing complete
zero-argument browser launcher on official packaged Chrome and Brave. It runs
when its workflow or vendor preflight changes (including initial branch
registration) and can also be dispatched manually. The original `CI` browser
job is unchanged.

Native mode requires `MTG_BROWSER_VENDOR=chrome|brave`, the corresponding
canonical ELF in `MTG_CHROME`, and `MTG_BROWSER_NO_SANDBOX=0`. It never discovers
or substitutes Chromium. Every nested browser launch now respects the existing
explicit `MTG_BROWSER_NO_SANDBOX=1` opt-in; native mode rejects that opt-in.

Chrome is reinstalled through its signed official APT repository, with Google's
active primary signing fingerprint checked. Brave is installed using
the vendor's [APT instructions](https://brave.com/linux/), not a remote shell
installer. Both binaries and their sandbox helpers must be root-owned package
files, with the helper installed mode 4755. The disposable runner's observed
world-writable `/opt` and Chrome directories are explicitly protected as
root-owned mode 0755; the vendor package restores its own file modes. No helper
chmod, local host installation, AppArmor change or sysctl workaround is used.

## Runtime Checks

Preflight checks package ownership, executable identity/hash, the running
process's DevTools product/version and a real DOM nonce. Informational `--version`
console formatting is not a native-acceptance predicate. It also checks the
browser's `chrome://sandbox` status for its first
sandbox layer, PID/network namespaces and seccomp. Chromium describes this as
the **expected renderer sandbox status**; the JSON explicitly does not claim
per-renderer kernel attestation. These are runtime prerequisites, not proof of
the game's correctness or a general security certification.

A non-root systemd service contains preflight and the complete launcher. Its
`KillMode=control-group` cleanup includes browser crash handlers even if they
create new sessions. The wrapper waits for service completion and rejects a
remaining populated cgroup. Its aggregate bound is 45 minutes; the launcher's
existing per-program bounds and ordered assertions are unchanged.

Only `preflight.json` and `lifecycle.json` are uploaded. Profiles, databases,
screenshots, game dumps, provider inputs and raw private traces are excluded.
Startup failures include the actual pre-cleanup exit state and a bounded stderr
prefix hash/count with fixed message classifications, never the original text.
Those classifications describe matched text, not a proven kernel/policy cause.
Counts cover observed pipe bytes only. Capture is released when the direct
child is reaped, and the report distinguishes EOF from deliberate pipe closure;
inherited descendant pipes cannot keep the observer alive.
The private browser scratch root uses a short `/tmp/mtg-v-*` path so browser
singleton sockets cannot overflow Linux's Unix-domain socket pathname limit;
metadata reports still remain in the explicit runner evidence directory.
Firefox needs its separate adapter and is not certified by this workflow.

## Local Checks

`npm --prefix frontend run test:unit:native-browser` exercises configuration,
status parsing, the actual nested launch argument expressions, browser
selection and a stubbed systemd invocation/cleanup. It does not start a browser,
install a package or execute a privileged service. Passing these checks is not
a substitute for a successful native workflow on the corresponding commit.
