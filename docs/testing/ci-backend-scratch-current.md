# Hosted Backend Scratch Retention

Published `a3694abc02cecfff18aa359292ee87c6621a5da9`, run38130914210,
passes frontend and the whole browser job. Backend job114444877173 fails with
a runner annotation reporting `No space left on device` while writing its
worker diagnostic log. No result artifact is uploaded. This establishes a
storage failure, not a backend pass or an observed gameplay-failure count.
The separate 2f18 backend job reaches the six-hour platform limit; neither
absence of metadata nor elapsed time identifies its last executed test.

The backend runner previously used pytest's default `all` temporary-directory
retention. The correction supplies only
`-o tmp_path_retention_policy=failed`, using pytest's built-in fixture lifecycle
instead of adding a directory scanner or custom deletion authority.
All original test discovery, ordering, assertions, observer hooks, private
inputs and exit-code precedence remain unchanged. Pytest documents these
retention settings in its [configuration reference](https://docs.pytest.org/en/stable/reference/reference.html#confval-tmp_path_retention_policy).

Two new real-runner regressions fail against the old invocation. A generated
public pytest scenario executes twenty successful scratch-producing cases,
one deliberately failing case and a final inspection. Previously all twenty-one
payload files remain. With the correction, only the failed-call payload remains:
peak sampled payload storage falls from5,505,024 to262,144 bytes. All22 collected
identities and66 setup/call/teardown records remain, with exactly one intentional
failure. The child denies SQL and sockets before importing pytest; no protected
trace or backend application is loaded. This is a small deterministic storage
reproduction, not a measurement of the failed hosted runner's peak usage.

The pinned pytest9.0.3 implementation removes passed-call `tmp_path` directories
during fixture teardown. It does not promise preservation for setup/teardown
errors, and session/module `tmp_path_factory` roots and manually created server
directories are not individually reclaimed by this option. Private phase and
failure ledgers remain outside pytest scratch. No assertion that all failure
files survive, that all leaked resources are closed, or that all hosted disk
growth is fixed is made.

The complete128-check CI-script suite passes in13.324s after updating both
original exact-command expectations for the intentional option. The earlier
127-pass/one-expectation-failure run is retained separately. No test selector,
skip, failure suppression, SDK root, capacity floor or runtime authority is
changed. Hosted execution on the corrected composition remains necessary;
all original release gates and measured AI-quality requirements remain open.
