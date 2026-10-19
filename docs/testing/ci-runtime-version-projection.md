# Optional CI Runtime Version Projection

The backend launcher already records `python-version.txt` and
`installed-packages.json` before pytest. The sanitized metadata converter
projects these existing snapshots into the optional `runtime_versions` field;
it does not import the application, inspect the converter's installed packages,
install dependencies, or change the workflow.

## Public Fields

- `observation`: `before_pytest`, not a post-test inventory or child inventory.
- `python_version`: the numeric version from the exact `Python X.Y.Z` producer
  line, or `null` when unavailable or invalid.
- `packages`: exactly the 28 canonical names in the reviewed Linux application
  closure, with observed release versions or `null`.
- `direct_packages`: the nine declared direct package names, not an assertion
  that their installed versions equal the requirements.
- `status`: `available` when all 29 observations are valid, `degraded` when only
  some are valid, or `unavailable` when none are valid.

The allowlist is explicit in the converter. Updating the reviewed package
closure requires updating its allowlist and tests. Package names are normalized
for case and the standard hyphen/underscore/dot aliases. Duplicate selected
names remain `null`, even if later duplicates contain valid versions.
Only bounded numeric release versions with conventional epoch, prerelease,
postrelease, and development suffixes are accepted. URLs, local/build tags,
arbitrary strings, unselected packages, and extra metadata keys are not exported.

Python input is limited to 128 bytes. Package input is limited to one MiB and
1,024 rows; individual versions are limited to 64 characters. Missing,
malformed, unreadable, oversized, or symlink snapshots never echo their values
or exceptions. A valid independent snapshot can still be retained when the
other snapshot is unavailable. Deeply nested malformed JSON cannot change the
core metadata result.

## Qualification Boundary

This field is an optional runtime observation, not lock conformance, binary
integrity, complete environment enumeration, or an advisory certificate. It
cannot change pytest exit status, coverage, metadata error codes, or CI success
qualification. An invalid source/evidence root can still fail before the
optional observation is reached. Existing archives without these snapshots
remain readable and explicitly report unavailable observations after source
validation. The launcher and its private full-package snapshot are unchanged.

The NEW synthetic privacy controls cover the actual 28-name lock roster,
missing and partial snapshots, unknown keys, duplicate aliases, version
validation, malformed and deeply nested JSON, symlink and size boundaries,
early ledger failure, and exact original exit/coverage/error parity after
removing only the additive field. They are not application or hosted CI tests.
