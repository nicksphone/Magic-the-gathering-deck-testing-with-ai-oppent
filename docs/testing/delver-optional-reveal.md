# Optional Private Reveal / Self-Transform

Isolated product repair over frozen human-ready source
`mtg-human-ready-composition-3eL65X`, plus the unchanged strict transform audit
`d5d843c30191d5c03539d6b118215fdb443d6626f0d16dd98d216532bf8ee7a3`.
No parent/main/live writes. No global day/night changes.

## Declared Product Seams

- NEW `rules_engine/optional_reveal.py`: full canonical own-upkeep instruction
  parsing, private look, explicit reveal/decline, typed transform condition,
  captured top/source references, and public pending-status projection.
- `events.py::_trigger_from_oracle`: replace only the old broad top-card transform
  shortcut; require a fully parsed instruction and actual controller UPKEEP.
  No ordinary trigger collection or oracle_effects changes. This is the isolated
  Sagan/Averroes coordination seam; parent should compose this narrow hunk only.
- `effects/handlers.py::transform_if_top_matches`: optional parsed payload delegates
  to the NEW helper; legacy explicitly mandatory helper payloads remain compatible.
- `keyword_actions.py::finish_mechanic_choice`: narrow continuation dispatch hook.
- `game_state/serializers.py::serialize_match`: optional-reveal pending status only.
  Private serialize/deserialize snapshots remain unmodified and complete.
- `frontend/components/Controls.tsx`: known-kind support and existing generic
  immediate-choice buttons. No App/client/shared driver changes.
- `frontend/types/index.ts`: pending/legal kind unions. `api/match-contract.ts`:
  owner/count/options/inspected-card shape safety for this new known kind only.

## Choice Contract

Existing `choose_mechanic` POST, `card_ids: ["reveal"]` or `["decline"]`, exactly
one explicit choice, owner from checked legal moves. Public pending status has
only kind/player_id/label/count. Owner legal view uses `optional_reveal`, the
existing `inspected_cards` CardView array and labelled reveal/decline options.
Other seat legal moves are empty while resolving. Private snapshot retains top
identity/incarnation/zone sequence, transform source reference and ordinary
resolving-item continuation. No private card name is logged or publicly observed
on decline. Reveal is legal even for an ineligible card; only a revealed qualifying
card transforms the same still-existing source incarnation. The top is not drawn,
reordered, or given alternative invented outcomes. Empty library finishes normally
without a fake acknowledgement choice. No response/priority window during look
and optional decision; the existing resolution continuation restores priority.

## Frozen Assertion Comparison

Original audit, fixtures and 166 PASS / 14 strict RED evidence stay unchanged.
NEW repair runner/probe extends its actual controls with reveal/decline paths,
private inspections, pending-choice process restarts, empty library and stale UI
409 rejection. Original non-choice control assertions and canonical facts remain;
original optional-choice/decline assertions are evaluated through newly available
real controls. "No fabricated POST" now proves actual explicit checked wire in
that branch, rather than forbidding all choice actions in the previously missing
branch. All original neither-designation expectations remain strict; global
failures are not xfailed, excluded, or disguised as transform success.

Separate explicit fixture correction: original setup cleared opening hand lists
and rebuilt library lists without resetting those card objects' zones. This made
some controlled library entries internally HAND-zone objects. Only the NEW
fixture wrapper moves actual canonical library-listed objects into LIBRARY before
any App action. No original fixture/evidence, Oracle, stats, colors, quantities,
assertion expectations or game history is rewritten. NEW empty-library setup
moves canonical objects to graveyard explicitly. This is not historical play.

## Qualification Commands

```sh
MTG_TEST_PYTHON=/external/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/external/frontend/node_modules \
node frontend/tests/browser-delver-repair.mjs
MTG_TEST_PYTHON=/external/backend/.venv/bin/python \
node --experimental-strip-types frontend/tests/optional-reveal-contract.mjs
/external/backend/.venv/bin/python -m pytest -q \
  backend/tests/test_optional_reveal_transform.py \
  backend/tests/test_transform_numeric_ai.py \
  backend/tests/test_cathar_day_night_linked_exile.py \
  backend/tests/test_top_card_choices.py \
  backend/tests/test_activated_top_selection.py \
  backend/tests/test_opaque_selection_http.py \
  backend/tests/test_trigger_target_choices.py
```

The dedicated 12-flow runner freezes source into fresh local SQLite/profile,
uses random loopback ports and owned root/token/PID guards, and archives private
actual requests/snapshots/screenshots on verified NFS before cleanup. Hosted
execution requires explicit RUNNER_TEMP archive storage. No live data or ports.
Final qualification/counts/hash paths are in the archived terminal report.

## Limits

Supported parsed family: full own-upkeep look-top / optional reveal / revealed
card-type condition / self-transform instruction. No named-card dispatch or
Oracle modification. No generic conditional-Oracle certification, other
compound clauses, multiple inspected cards, alternative effects, meld/flip,
or blanket card coverage claim. Canonical Delver and existing Cathar controls
are the actual human qualification corpus. AI strategic reveal/decline ranking
is outside this human repair and needs separate consumer qualification.

Delver triggers at UPKEEP, as its pinned raw Oracle says. Day/night's unrelated
neither-start semantics and its untap-versus-upkeep ordering gap remain unfixed;
those require a separately declared global turn-based scope, not this partial
repair. Authority: [official September 25, 2026 CR](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
503 (upkeep) versus 731.2 (separate day/night untap check).

The final inspection wording is qualified separately with
`node frontend/tests/browser-delver-repair.mjs --inspection-copy`: exactly two
both-seat ineligible-card flows, not a shortened twelve-case success claim.
The complete twelve-flow run and this later display-only copy check retain
separate private archives/source manifests. Global neither-start REDs remain
strict in both scopes. Original 180 assertion names/counts were mechanically
compared: all 166 original PASS controls retained, eight Delver REDs now PASS,
and the six original global REDs remain; no original assertion was removed.
