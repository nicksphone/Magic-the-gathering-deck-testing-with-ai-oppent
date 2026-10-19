# Production AI knowledge consumer audit

## Frozen Scope

Tests/report only, 2026-10-06. Input qualified-composed-source.tar.gz SHA256
`8803395e874f92e939aaa4b68d7da4ece543ffe49b61f59b547fd3d4f15c305c` from
combat-read-scope-reuse/mtg-combat-read-scope-source-xyWrS9. That small experiment
is not a promoted-main or playing-strength claim. Original source hashes are
unchanged. Agent SHA256: `8b1d9a07d7a60267403096350bfa5edc69bc70786fb748576881eba2f30890aa`.
No production, Oracle, training, planner, budget, dependency or parent writes.

Built-in full canonical Tempo, Dimir Control, Ramp and Tokens decks are hydrated
through the real committed card source. Source IDs, full Oracle, quantities,
faces and deck analyses are in private receipts. Explicit synthetic positions
use seed701 and both seats; battlefield setup is not a claim of natural ETB or
historical reconstruction. All libraries and opposing hands are opaque to the
teacher. Metamorphic tests reverse unseen libraries and swap genuine opposing
hand cards without changing public counts. Selected own-card surfaces are not
hidden-library knowledge. Memory Deluge persisted-facts control uses the full
committed fixtures/opaque_selection/memory-deluge.json, not invented Oracle.

## Results

- New audit whole module: **13 PASS, 10 ordinary RED**, 1 warning, 3.61s, exit1.
- Six whole neighbor modules: **65 PASS**, 7 warnings, 2.58s, exit0.
- Four bounded actual MASTER chooser calls: Tempo/Ramp and Control/Ramp, both
  seats, seed701; all exit0, legal checked actions, root/privacy/restore parity.
  No planner override, new games, retries, profiling or performance claims.
- Tempo selected legal Petty Theft, face1, targeting opposing Topiary Stomper.
  Control passed with its known Counterspell held. No dominated final decision
  is established by these four observations.
- Ramp/Tokens use actual teacher classification, scoring, cost/materialization
  and checked-action probes, not additional full-master observations.

The initial audit is immutable in initial-audit/: 11PASS/12RED. Two failures were
incorrect control expectations that hybrid_choices had to be emitted by AI.
The actual checked Spectral Procession action uses cost_choice.id=base; the
engine resolves the sole affordable WWW branch and taps three Plains. These
were corrected test assumptions, not product bugs. The ten desired REDs remain
ordinary failures unchanged. Privacy was strengthened with an actual unknown
opponent hand, and lost response affordability independently checked after draw.

## Concrete Findings

1. Four selected-face REDs (two seats, race/convert roles): Stomp's selected face
   has burn, but `_matchup_move_adjustment` uses the stored Bonecrusher Giant
   front. Actual adjustment0.175 versus1.475 when the SAME consumer reads the
   authoritative selected face. `_rank_moves_query`, `_cast_bias` and
   `_materialize_action` already use `_card_for_move`. Checked actions correctly
   preserve face1 and targets. This is a component metadata-binding mismatch,
   not proof of a lost game or dominated final move.
2. Two reservation REDs: legal Petty Theft can answer the public opposing
   creature before Consider. Consider spends the sole blue mana, making that
   response unpayable. Actual `_instant_value_reservation` returns0 rather than
   a negative hold value: it filters stored Instant cards, and legacy tactical
   tags also do not recognize bounce as removal. Standard Counterspell controls
   return-6 during opposing main and0 at end step. A front-type-only correction
   would not address the second omission. Actual full Tempo teacher still
   chooses the bounce in these witnesses, so no harmful final choice is claimed.
3. Four own-hand extra-land classification REDs: Growth Spiral tags draw only;
   Arboreal Grazer has no ramp tag. Separate BOTH-seat checked resolution receipts
   also show frozen-engine clause omissions: Spiral produces only draw_cards;
   Grazer enters then produces a noop ETB. Known Forest remains in hand with no
   land-choice continuation. These are not solely AI metadata defects: assigning
   stronger tags alone could value effects this frozen engine does not execute.
   This is a pinned-source finding, not a claim about moving main.

## Actual Dataflow And Minimal Recommendations

Repository/CardKnowledge canonical card_data is consumed by hydration through
canonical_local_profile and reaches MatchFactory runtime card facts. This route
works. Optional persisted play_value/threat_level/cast_windows are not transferred
or consumed; their model explicitly calls them future profiles. Controlled
changes to those optional annotations do not alter hydrated facts. This is
intentional current nonconsumption, not a broken promised integration.

Canonical tactical metadata includes per-face tags and mechanic surfaces, but
mechanic_metadata says semantics not_evaluated and execution_support unknown.
The AI currently reparses tactical tags, uses analyze_deck classifications,
profile_for matchup scalars, public board roles and real cost/materializer
helpers. Full MASTER delegation receipts prove these methods are called, not
merely imported: Tempo counts rank2/tags26/castbias2/matchup6/reservation2/
materializer7/passbias2; Control counts2/21/1/5/1/7/2.

Recommended future narrow scope, NOT implemented:
- Bind matchup cast adjustments through existing `_card_for_move`, as sibling
  consumers already do; no name dispatch or new weights.
- Enumerate authoritative actor-owned cast surfaces/costs for reservation,
  including supported Adventure interaction, using existing legality/payability
  helpers. Recognize supported interaction effects without trusting arbitrary
  surface tags. Preserve legitimate deployment/end-step controls; no blanket
  hold, self-target ban or hidden opponent forecast.
- Coordinate extra-land canonical execution before independently changing its
  scoring tags. Keep provenance, semantic support and optional quality distinct.

## Reproduction

Use the input tar above plus this three-NEW-file patch, fresh local SQLite,
external qualified Python; no databases on NFS. From backend:

```sh
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q \
  tests/test_ai_knowledge_consumer_audit.py
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q \
  tests/test_deck_analysis.py tests/test_tactical_tags.py \
  tests/test_ai_oracle_semantics.py tests/test_card_hydration.py \
  tests/test_knowledge_models.py tests/test_mechanic_metadata.py
```

`PY` used: /home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python.
Raw actual-master scripts/config/actions, legal/scoring receipts, checked clause
resolutions, JUnit, exits, initial failures and input/source manifests are private
NFS evidence. They are synthetic debug receipts, not inputs exposing hidden
cards to policy. No raw user game data was read. Exact hidden-order/hand,
root, legality and restart equality is tested; no blanket modal/special-cost,
all-deck, neural, expert-strength or win-rate certification.

Graph maintenance: own-root AST update reached1600/1600 files but the 30s bound
ended exit124 before full graph completion. No parent graph writes; no freshness
claim. Evidence includes the partial update log.
