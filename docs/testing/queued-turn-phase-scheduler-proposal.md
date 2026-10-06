# Queued Turn/Phase Scheduler Proposal

STATUS: historical design, now implemented for the bounded families below in
the unreleased integration candidate. This document retains the original
proposal rationale; its baseline/red counts are historical, not current status.
Current coupled qualification remains pending; see
[the current candidate record](queued-global-lazy-current.md).
Baseline is frozen M+nth with qualified admission safety, not moving parent.
The source has fixed TURN_STEPS and no admitted insertion queue. The ten
historical scheduler contracts remain ordinary red. Do not relax safety markers
until actual full-schema runtime admission and tests exist.

## Rules And First Admission Boundary

Use the pinned [official CR effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
from the immutable audit archive (SHA256
8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca).
CR 500.7 inserts extra turns after the specified turn, newest creation first.
CR 500.8 similarly inserts phases after their anchor phase. CR 505.1a makes
additional main phases postcombat main phases. CR 302.6 uses continuous control
since a controller's most recent turn began, not simply a numeric turn counter.
CR 502/504 provide actual beginning-phase untap and draw actions; an additional
combat/main pair does not include a beginning phase. CR 514's cleanup completion
must finish before consuming the next turn. Use existing priority/stack rules,
not queue consumption at the first pass, end step or first cleanup attempt.

First two generic, full-clause schemas only:

- Target/controller gets one extra turn after this turn.
- Paid sorcery-timed activated ability untaps controlled creatures and inserts
  combat followed by postcombat main after this main phase.

Preserve the full authentic Oracle and costs, including any extra instructions.
Do not admit skip-untap, lose-at-end-step, multiple/future-anchor turns, turn
ending, player-turn control or unexplained clauses merely because an initial
phrase resembles these schemas. Broader schemas require separate qualification.
Time Warp and Aggravated Assault are witnesses, not name dispatch.

## Minimal Authoritative State

Keep one RulesEngine and the existing step actions/stack/continuations. Do not
add a parallel effect or simulation engine. Proposed persistent fields:

- A normal-turn successor cursor, independent of the actual outgoing actor.
- A newest-first list of extra-turn entries: recipient, current-turn anchor,
  stable creation ordinal and public/last-known source provenance.
- A per-turn phase plan/cursor with unique phase-visit IDs; each combat frame
  contains the existing combat steps, each main frame has one main phase.
- Ordered insertion groups anchored to a phase visit. Each group preserves its
  internal combat-then-main order; newer groups precede older groups at the
  same anchor. No RNG, hidden identity or executable callback in queue entries.

An extra turn increments the actual turn ordinal and resets per-turn state,
but does not consume the normal successor cursor. After pending extra turns,
the previously scheduled next normal player still gets their normal turn.
Always alternating from the extra-turn actor would drop or misassign turns.
The next turn's active player must be chosen before normal untap/upkeep/draw.

Inserting a combat/main pair after precombat main must leave the original
combat/postcombat main reachable afterward. Inserting after an extra main must
not lose the remaining ordinary phase plan. Repeated activations resolve to
whole insertion groups, not reversed individual phases. Never fake an extra
combat by changing only state.step or turn number.

## Resolution And Timing

Use existing effect registry and continuation conventions. Create an insertion
only on actual successful resolution. Countered/fizzled spells create none;
real copied spells/abilities can insert on resolution but do not increment cast
counts. Capture the actual announced recipient/controller and source identity.
Source departure after activation must not cancel an otherwise legal ability.
Keep public prohibitions, legal targets, sorcery timing and all payments intact.

The controlled-creature untap is a real instruction evaluated against current
effective types/control at resolution. Reuse existing untap/replacement/stun
handling; do not untap lands/opposing creatures or clear summoning sickness.
No invented default token or future card. Only after the entire activated
instruction is represented should its admission marker be removed.

## Existing Lifecycle Interactions

Each combat visit resets attack/block declarations, targets, bands, assignment
queues and first/double-strike damage stage appropriately. Expire end-of-combat
effects at the actual combat boundary, not end-of-turn effects. Preserve turn
history across additional combats; audit aggregate attack/trigger counts rather
than assume all current fields are visit-safe. Mana empties at real step/phase
boundaries using existing rules. SBA/APNAP/deferred choices keep their existing
order and cannot cause the phase cursor to advance twice.

Per-turn cast counts reset only at actual new turns, including extra turns;
additional phases retain them. Capture the outgoing actual active player's
count for day/night before reset. Foretell, Suspend, upkeep and draw triggers
use actual step entry exactly once. Preserve land limits, loyalty limits,
temporary permissions, damage and cleanup-repeat behavior at their real
boundaries, not on each extra combat.

Audit controller-continuity/summoning-sickness semantics explicitly. A creature
that entered during the prior turn may become usable on that controller's extra
turn, but another player's turn is not that controller's new beginning. Extra
combat alone never cures sickness. The current numeric entered_turn approach
must not be treated as proof of arbitrary control-change fidelity.

## Restore And Privacy

Serialize queue entries, phase plan/cursor/visit IDs, creation ordinals and the
normal successor cursor in the authoritative snapshot. Reject malformed or
contradictory persisted plans; do not silently discard queues. Old snapshots
without new fields can reconstruct the ordinary fixed plan only, with an
explicit compatibility version/default. Restore does not replay effects or
re-fire already-entered step actions. No callable/pickle callback schema.

Queue provenance is public or last-known resolving-source data, not an
opponent hand/library identity. Actor-private prompts and existing continuations
remain private. Request rejection and reads must preserve the complete original
root/RNG/config/SQL. Compare restored canonical data and the actual state,
not just narrative logs. Keep both-seat actual HTTP/process restore cases.

## Proposed Scope And Acceptance

Before implementation, separately declare a narrow new scheduler helper plus
game_state/state.py, serializers.py, rules_engine/engine.py, the effect-registry
adapter and the exact admission/compiler changes. No AI, information, mana,
events-owner, schema or API edits without separate demonstrated necessity.
Keep parser/admission/effect/state evidence distinct.

Required desired contracts: both target choices/controller arrangements;
newest-resolution-first multiple turns; normal successor continuity; copied,
countered/fizzled sources; pre/post/extra-main pair insertion; repeated activation;
real untap/draw/sickness; first-strike combat reset; cleanup repeat/SBA/APNAP;
actual cast-count/day-night/foretell/Suspend continuity; pending prompt/stack,
queued-effect and mid-phase fresh-process restore; immutable rejected root;
hidden-order invariance. Canonical real fixtures only. Existing historical ten
red tests become actual green runtime evidence, not relaxed expectations.

Stop first-family admission if ordering or restore remains unproven. Keep
unsupported markers for all other scheduling procedures. No natural-game
strength, expert-policy, win-rate or full-CR completeness claim follows merely
from a scheduler or parser being present.
