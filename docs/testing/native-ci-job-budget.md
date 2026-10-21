# Native CI Job Budget

The native browser service retains its 2,700-second runtime limit and
15-second stop limit. The hosted job has a separate 60-minute limit, leaving
15 minutes for checkout, dependency/vendor installation, metadata upload and
runner finalization outside the service. This reserve does not extend any
browser program, gesture, game, AI or service deadline.

On `daec6c45`, native jobs `118133537524` and `118133538157` were cancelled
with GitHub's 45-minute job-limit annotation. Both suite and metadata-upload
steps succeeded first. Their allowlisted lifecycle records report exit zero
and empty cgroups; vendor preflight passed with sandboxing enabled. Those
component observations do not override the cancelled overall job outcomes.

The workflow previously gave the entire job the same 45 minutes as its
service, without a setup/finalization reserve. A finite unit contract fails
on that header and passes on the 60-minute header. The launcher, its service
and stop clocks, scenarios, sandbox and metadata allowlist are unchanged.

This corrects the outer CI budget, not an application bug or an intermittency
claim. The new head still needs actual complete hosted job success. Earlier
cancelled jobs are retained as cancelled, never relabeled as passes.
