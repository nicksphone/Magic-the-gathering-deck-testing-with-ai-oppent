# Coupled and Independent Target Fidelity

Status: reproduced gaps; implementation and acceptance remain open.

## Evidence and boundary

Strict action reconstruction rejects three retained casts that announce a
player without the required creature. These records must remain failures.
A separate canonical Searing Blaze probe supplies both targets, but the current
inference builds ordinary and landfall damage instructions together, directs
both at the creature and deals no damage to the player. An Agony Warp probe
correctly applies both modifiers to one creature; it does not establish
independent choice of two different recipients.

Raw Scryfall fixtures are retained in the isolated `codex/coupled-targets`
worktree. No printed card characteristics or competitive decklists are invented.
The probes exercise inference/effect handlers, not a complete HTTP/UI game.
Retained probe setup errors are not engine failures.

## Implementation Sequence

1. Introduce an ordered target-instance contract for repeated occurrences of
   targeting language. Reuse existing modal/clause assignment and incarnation
   tracking rather than maintain separate card-name exceptions. Validate the
   complete announcement before paying costs or mutating authoritative state.
2. Represent dependencies between instances, such as a creature controlled by
   the chosen player or by the chosen planeswalker's controller. Admission,
   legal hints, AI materialization, spell copies and resolution must use the
   same dependency model. Never substitute a newly convenient target.
3. Preserve turn-local land-entry history from all battlefield-entry sources,
   including effects and entries whose land subsequently leaves play. Playing
   a land is not the only qualifying event. Serialize the ledger and reset it
   at the turn boundary without changing land-play allowances.
4. Select conditional damage at resolution and apply each target's damage in
   the same instruction batch. Ordinary and replacement landfall branches are
   alternatives, not consecutive instructions. Reuse the existing prevention,
   replacement, trigger and state-based-action machinery.
5. Support independent P/T-modifier recipients. Distinct target instances may
   name the same creature when the text permits it; explicit distinctness
   requirements remain enforced for the existing counter-allocation family.
6. Preserve legal portions when only some targets become illegal. Test changed
   control, departure/return incarnations, protection, hexproof and target
   dependency with last-known information where applicable. Revalidate actual
   targets rather than require an entire old candidate list to remain available.
7. Expose instances and dependencies through typed HTTP legal hints and shared
   action schemas. Make AI choices with checked payment and public information.
   Add human group controls or an explicit unsupported-action warning; a backend
   repair alone must not be labeled a completed human workflow.
8. Re-run strict reconstruction and fresh seed/seat-balanced matches with full
   legal-action traces. Changed-source replay drift is expected where behavior
   is repaired; distinguish that from current-source repeatability failures.

## Acceptance Checklist

- [ ] Both seats: canonical Searing Blaze admits exactly its required pair,
  rejects missing/wrong-controller targets and is unavailable with no legal pair.
- [ ] Ordinary and landfall amounts differ correctly; no-land, played-land,
  effect-entry, departed-land, next-turn and snapshot-resume cases pass.
- [ ] Player and planeswalker alternatives are exclusive within their instance,
  but do not exclude the second required creature instance.
- [ ] Canonical Agony Warp supports shared, different and reversed recipients;
  actual stats, combat, cleanup expiration and restart agree.
- [ ] Each family handles one/all illegal targets, controller changes, return
  incarnations, copies and replacement/trigger continuations through the stack.
- [ ] Malformed HTTP announcements are structured 4xx with unchanged state,
  RNG, payments, logs and database snapshots.
- [ ] AI announces legal complete targets for both seats and does not repeatedly
  attempt an unavailable pair; UI controls preserve deliberately chosen targets.
- [ ] Focused fixtures, full isolated suite, appropriate browser actions and
  fresh repeated matchup traces pass before the capability is called complete.

## Rules References

The [official rules page](https://magic.wizards.com/en/rules) currently links the
[September 25, 2026 Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).
Rules 115.3, 601.2c and 608.2b govern target-instance selection, complete
announcement and resolution with some illegal targets. These requirements
inform the contract; parser recognition is not proof of rules fidelity.

## Known Limitations and Next Upgrades

The current action shape and clause mapper do not establish arbitrary multiple
target-instance support. Conditional Oracle instructions need semantic checks,
not merely clause splitting. This bounded two-family batch is groundwork for
broader targeting, not certification of every compound Magic spell.
