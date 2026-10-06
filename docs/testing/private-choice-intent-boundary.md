# Private Choice Intent Boundary Audit

NEW tests only, over frozen `Cc4vy3` backend/frontend source fingerprint
`5243c8dc8f7d9c7b4348b09047578d29efc980eb2b215fbf20dbf5dd79bd506a`.
No production, metadata allowlist, existing fixture, App or shared-driver edits.
Two canonical families: Delver optional private reveal and Recruitment Officer
private top-four selection. Existing committed raw fixtures/helpers reused;
explicit retained positions are not natural histories or built-in deck claims.

## Findings

1. Whole actual owned legal views plus an explicit selection are rejected by
   `TrainingEnvironment.lookup_intent`. Both seats, selection and decline.
   Delver views include `inspected_cards`, `inspected_card_ids`, `effect_payload`
   and `top_reference`; Officer views also include bottom flags and `top_ids`.
   The mechanic display/context sets do not recognize these fields. Raw action
   API rejection of whole view packets is intentional and remains a green control.
2. Known choice fields with malformed null/nested values reach `complete_action`
   before it rejects them. Unknown top-level/null fields and forged pending
   contexts DO reject before the helper. No execution/root mutation from those
   malformed selected payloads was observed.
3. `choice_id: null` or `damage_assignment: null` alongside valid explicit
   `card_ids` is accepted by Training and raw API. The current model explicitly
   permits optional null fields and counts non-null payloads. This fails the
   requested stricter null-rejection boundary, but is NOT branch steering,
   guessed selection, wrong-seat execution or a discovered private-data leak.

Proposals, NOT implemented: separate owned display from exact-match pending
continuation context in the mechanic intent adapter; validate chosen payloads
before the completion helper. Private top/reference/continuation fields must
not be blindly allowlisted. If explicit-null rejection is intended, coordinate
the `MechanicChoice` presence validator with existing callers/contract ownership;
otherwise document nullable sibling tolerance. Do not broaden raw API metadata.

## Qualification

Strict combined NEW 100-case gate: 60 PASS / 40 RED, 100.08s, exit 1. No xfails,
skips, omissions or changed expected assertions. Guarded NEW unit gate and
receipt-backed real HTTP sidecar are independently frozen in terminal evidence.
Two additional both-seat alternate Officer controls PASS, preserving selection
of Militia Bugler rather than the first eligible Savannah Lions option.
Unchanged four-module neighboring gate: 149 PASS, 31.72s.

Real HTTP sidecar: eight explicit selection/decline positive flows PASS through
two backend process restarts each; eight whole-view intent cases remain RED.
It uses a NEW guarded test-only bridge to call the actual Training adapter over
restored state. Production action/restore/legal-view handlers remain unchanged.
This is not a claimed production Training HTTP endpoint or an actual-App rerun.

Positive controls include owner/private observations, other-seat legal-view
absence, exact pending-context checks, malformed raw API rejection before engine,
minimal action normalization, deterministic state/RNG replay, stale-action 409,
snapshot/controller/SQLite dump equality across rejection and real process
restart. Foreign hotseat hands in ordinary match responses are not treated as
a new client-authentication guarantee. Private receipt logs stay in evidence.

## Safe Reproduction

Use a fresh LOCAL source-only checkout, excluding DB/cache/dependencies and Git.
The unit audit requires an explicit matching marker before any API fixture runs:

```sh
printf '%s' "$PWD" > .private-choice-audit-source
MTG_TEST_PYTHON=/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python
"$MTG_TEST_PYTHON" -m pytest -q -s \
 backend/tests/test_private_choice_intent_boundary.py \
 backend/tests/test_private_choice_http_restart.py \
 backend/tests/test_private_choice_alternate_control.py
```

Do NOT create that marker in main/live. A tracked Git checkout is rejected.
The real-HTTP fixture independently creates fresh local source/SQLite with a
singleton token/root guard, random loopback port, bounded owned process restart,
and private actual request method/body/response receipts. It retains completed
runtime evidence for the caller to archive/verify before cleanup, including REDs.
No foreign services or SQLite databases are read, copied or killed.

No default CI/npm alias changes. This strict audit intentionally contains RED
expectations and must not be presented as a green release gate or silently
merged into ordinary CI before the findings are resolved/requirements decided.
No new canonical metadata or blanket card/mechanic certification.
