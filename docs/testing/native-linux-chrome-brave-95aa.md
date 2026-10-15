# Native Linux Chrome And Brave

Exact source `95aa731e5df4365e465058e8c3ee438d2ea5a973` completes native run
`38694364310` successfully. Chrome job `116287361914` and Brave job
`116287362029` each execute the same **45 stage headers and 501 PASS banners**.
Stage names and order match, and the unchanged launcher declares 68 program
executions. No focused subset was selected.

Each vendor's preflight succeeds, binds the driver and preflight hashes to the
exact Git source, and records `sandbox_disabled=false`. The actual installed
packages are Chrome `155.0.8059.79-1` and Brave `1.97.57`. Both lifecycle
records report exit zero and an empty enclosing control group. Renderer
sandbox status is browser-reported expected status, not an independent
cryptographic renderer attestation. No sandbox, kernel-policy or helper-mode
workaround was introduced.

The corrected fault injection lets CORS preflights proceed unchanged, opts
actual POST requests into response capture, and joins native continuations
within the original deadline. Late native errors remain fatal. Independent
artifact reconciliation counts the actual browser-only logs; pure protocol
tests are not substituted for this execution.

Private immutable evidence is under
`diagnostics/ci/native-chrome-brave-95aa-qualified-20261015-oQ7S16Ky/` in the
project NFS archive. The complete metadata ZIPs contain only preflight and
lifecycle JSON. Browser logs remain private evidence; no raw backend log or
protected game trace was fetched. Earlier failed Brave runs and the late-ACK
regression ledgers remain separate and immutable.

This qualifies only the stated Linux native Chrome/Brave source component.
It does not qualify Firefox, remote LAN HTTPS trust, later knowledge-model
changes, complete AI measurements or the full release. See
[Firefox integration](firefox-transport-integration.md) for its open native
capabilities and launcher/cache requirements.
