# Explicit Native App Checkpoints

The opt-in Forge table can save a pending human choice, stop its worker and
reconstruct that saved point in a fresh worker. This is explicit saving, not
automatic persistence after every move, general engine adoption or AI-strength
acceptance. The live operator runtime is not switched by this source change.

The Forge Team/Card-Forge contributors provide the native rules, cards, baseline
AI and worker interfaces. The shared checkpoint store retains its GPL-3.0-or-later
notice; see [third-party notices](../../THIRD-PARTY-NOTICES.md).

## API And Recovery

Both endpoints require the existing session capability and strict request fields:

- `POST /forge/sessions/{id}/checkpoint`: `sequence`, `request_id`, `action_id`.
- `POST /forge/sessions/{id}/resume`: `sequence`, `action_id`.

The eleven-field snapshot stays unchanged. New statuses are `suspended` and
`restoring`; neither offers answerable choices. GET never starts a worker.
Checkpoint acknowledgement, its byte digest and the private checkpoint schema
are checked before durable publication. Suspension is reported only after the
reader, direct child and observed descendants have ended. A native refusal or
precommit save failure preserves the pending choice and previous saved point.

Resume restores original inputs and semantic start tickets, including starts
whose outer call has not yet returned. It uses only uniquely matching current
descriptors and fresh wire tokens. It does not wait for an outer completion
before answering a nested dialog. The full newly captured frontier must match
before any resumed choice is exposed. Unmatched or ambiguous replay fails closed
without overwriting the checkpoint. Starts are invocations, not successful casts
or payments.

Runtime configuration still accepts the original four fields. An optional
operator-only `causal_verifier` argv may permit the existing Java-proven completion
arrival-order exception. Without it comparison is strict; this is not permission
to ignore different cards, RNG, payments, pending inputs or native state.

Capabilities, build IDs, action fingerprints and receipts remain bound to the
same session across a host restart. A durable epoch keeps versions monotonic.
Uncommitted resume-metadata failures roll back the in-memory control; committed
but uncertain writes are reconciled before retrying. Old IDs do not dispatch a
second human answer. An explicit close durably abandons a save; shutdown keeps
the last saved point. If abandonment cannot be published, the worker is still
stopped and the API reports uncertainty rather than claiming durable deletion.

## Operator Storage

For a configured `sessions_dir=/local/path/sessions`, stable metadata and checkpoint
generations live in `/local/path/.sessions-saves`. This sibling is not mounted
writable into a worker. It holds an owner-only OS lease, preventing another
manager from starting against that save root. Runs and saves stay on local disk,
never NFS. Files are owner-only, bounded, no-follow and atomically published;
each resumed worker gets a new private directory instead of overwriting journals.

Build compatibility uses the trusted operator-provided build ID. This host does
not cryptographically attest classpath contents or negotiate a new native build
handshake. Preserve old saves and their matching runtime; do not relabel them
with an upgraded profile's ID. Browser requests cannot select commands or paths.

## Verification Scope

The final seven whole backend modules execute **258 tests**, all passing with
zero skips and unchanged source hashes. They include 65 existing owner tests,
121 unchanged checkpoint/prefix tests, 20 repository tests, 27 route tests and
25 new real-child checkpoint transport tests. The transport fixtures are clearly
synthetic and do not certify card rules or AI competence. A pre-import audit hook
observed no SQLite or network calls in this parent test process; that hook is not
claimed to be inherited by child interpreters.

Independent existing-store/client/profile baseline: 211 passing tests. The
frontend checkpoint cohort separately passed 51 Node tests. The complete
frontend package test chain passed 1,047 TAP tests plus its non-TAP assertion
programs; lint and the production build passed. The 51-test cohort is part of,
not additional to, the 1,047. These are not rendered-browser acceptance.

The first real-native manager smoke matched a checkpoint after three human
invocations, cold-resumed it with fresh tokens and advanced to a fourth invocation.
Its immediate descendant-closure check failed; a later quiet observation does
not turn that original result green. A synthetic detached-child regression
reproduced early suspension reporting. The correction waits for observed PID /
start-time identities and reaps only those exact children if adopted, without
global process signalling or subreaper changes.

The subsequent independent manager smoke passed with the corrected explicit
shutdown path: exact frontier, fresh tokens, a fourth native start and immediate
absence of all observed native process identities. A further regression covers
natural completion when a detached child does not inherit the transport pipes.
Owner finalization now performs the same bounded descendant cleanup before
publishing a completed result or freeing capacity. Native results for the final
owner revision are recorded separately, not inferred from the prior smoke:
the final manager smoke passed in 60.59 seconds on owner SHA-256
`3d439947f968e6bb04498b60a8c9279b30cc393d9b2f7b571f840cca44484178`.
It again verified the exact three-start frontier, fresh tokens, a fourth native
start and immediate absence of all six observed native process identities.
Both worker lifetimes loaded the thirteen-source token/return candidate. This
was a fresh manager in the same harness process, not a backend-process restart.

Full rendered-browser cold resume to a natural outcome, automatic crash-safe
per-action persistence, durable BO3, old-build migration, deployment and broad
strategic quality remain separate requirements. Checkpoint success does not
establish that the improved native AI is finished.
