# Private Choice Consumer Correction

Isolated correction over the frozen Cc4vy3 private-choice audit source archive
`c56374bc1dee48b28207b0c8d9c3a13125b27bd4f2ede6bd7bfa6a7f834b9c31`.
The original audit patch/report/evidence remain immutable on NFS. The older
`private-choice-intent-boundary.md` describes that original RED audit, not this
correction's qualification. This delta does not duplicate the audit file adds.

## Product Scope

Only `TrainingEnvironment.lookup_intent` in `backend/training/environment.py`.
For mechanic intents, supplied display/private inspection metadata must exactly
match the current actor's authoritative legal view. Continuation context must
exactly match owned pending state. Comparisons are JSON type-sensitive, legal
view construction uses a state copy, and absent/foreign/stale metadata rejects.
Metadata is not execution input. Chosen parameters are validated by the existing
public `MechanicChoice` model before `complete_action` receives them. The normal
checked trial execution remains the authority for legal selections.

The consumer never selects from options or infers a decline. Strict raw API
action bodies still reject whole legal-view packets. No action schema, helper,
API, engine, AI policy or frontend edits; existing invalid-AI sentinel and
unknown-field/context guards remain.

## Explicit Audit Compatibility Adaptation

The original BAD_FIELDS matrix conflated malformed/null-only selection with
nullable sibling fields alongside a valid explicit `card_ids` selection. The
public model allows `choice_id: null` and `damage_assignment: null` in the latter
case. This is intentionally unchanged, not claimed fixed or newly unsupported.
Two test functions keep their full original parameter matrix: exactly 16 cases
(two nullable siblings x two families x two seats x Training/API) now assert
the declared compatibility rather than rejection. Training preserves the
explicit selection and root; API executes the explicit decline. All other
original assertions/cases remain, including malformed selection rejection
before the helper/engine. No tests removed, skipped or xfailed.

## Qualification And Limits

Canonical Delver optional private reveal and Recruitment Officer private top-four
selection, both seats, explicit selection/decline and non-first selection. Reuse
existing canonical fixtures/helpers; no card/Oracle/choice fabrication. New
negative controls test every recognized display/context field with null/nested
alias tampering and malformed chosen parameters before completion. Positive
controls cover actual raw legal views and sanitized policy prompts, source/root
immutability, wrong seat, stale view/revision, hidden information, state/RNG
replay and actual loopback HTTP backend process restarts with SQLite receipts.

The HTTP Training route is the frozen guarded test-only bridge, not a claimed
production Training HTTP endpoint. Retained explicit fixture states do not
certify natural game histories, built-in deck admission or Training provenance
restore. This does not rerun actual App workflows or broaden hotseat HTTP
authentication guarantees. Frozen gate counts/timing, source hashes and private
receipts are in the terminal evidence; no claim beyond these two families.

## Reproduction

Use a fresh local source-only copy of the dependency, apply the product patch
then the separate tests/docs delta. Exclude all SQLite/cache/runtime/dependencies
and `.git`; never point fixtures at live SQLite. External Python is required.

```sh
printf '%s' "$PWD" > .private-choice-audit-source
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q -s \
 backend/tests/test_private_choice_intent_boundary.py \
 backend/tests/test_private_choice_http_restart.py \
 backend/tests/test_private_choice_alternate_control.py \
 backend/tests/test_private_choice_consumer_correction.py \
 backend/tests/test_private_choice_consumer_http.py
```

Fixtures use fresh local SQLite and random loopback ports, stop only spawned
process groups, and retain private receipts for NFS archival/verification before
cleanup. NEW test functions and the marked audit must not run on a live checkout.
