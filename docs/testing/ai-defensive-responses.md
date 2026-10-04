# Defensive resources and announced combat interactions

## Implemented Scope

The defensive blanket pass is removed. Master/Master-plus compare declared
combat responses through live stack resolution and remaining combat damage,
including the priority window between first-strike and regular damage. Hostile
pumps, removal, counter targets and counter wars are evaluated as announced
effects, not guessed from opponents' hidden hands.

One shared targeted-buff parser recognizes signed temporary stats with optional
fully recognized keyword grants. Both clauses resolve through existing handlers
and timestamp/expiry layers. Adamant Will and Moment of Heroism are canonical
examples, not card-name dispatches. Unknown keyword tails, ward grants in this
form and unparsed trailing instructions are not silently truncated.

Resource valuation discounts spent known hand cards and does not price temporary
stats, keywords, control or crewing as permanent board gains. Life utility is
diminishing at surplus totals and steep at scarce totals: an AI heuristic, not
a rule change. Phyrexian payments still use the real cost engine. Win/loss
outcomes outrank utility; small gains do not automatically justify spending cards.

Legal recipient and stack-target alternatives are shared with combat setup.
Public bounce can add a known card to hand. Hidden draws, library information,
unresolved choices or unsupported effects make a projection unknown. Six
creatures, sixteen candidate moves and sixty-four materialized actions bound
search; exhaustion is not certification of a partially explored optimum.

First-strike grounding: rule 510.4 in the [current Comprehensive Rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt).
Eight normalized fresh Scryfall responses are byte-checked against retained raw
responses; other canonical cards reuse existing fixtures. Shelter is retained
as corpus data, not claimed newly implemented. Test tokens come from Raise the
Alarm's parsed instruction, not invented cards.

## Acceptance Checklist

- [x] Reproduce sixty-six failures in seventy-two corrected original-source cases.
- [x] Execute fixed/devotion/compound pumps in both seats and six archetypes.
- [x] Verify indestructibility, lifelink and expiry without dropping clauses.
- [x] Handle both roles between strike steps and existing marked damage.
- [x] Answer hostile pumps/counter wars through actual announced stack targets.
- [x] Prefer removal when it additionally preserves the blocker.
- [x] Prevent a known loss with public bounce and no hidden-card inspection.
- [x] Preserve cards for wasteful protection or disposable-token trades.
- [x] Execute Phyrexian payments at healthy versus critically low life.
- [x] Reject certainty from draws, replacements and sixty-five spell copies.
- [x] Verify hidden hand identity does not alter the public response policy.
- [x] Verify HTTP payment, snapshots, restart recovery and subsequent damage.
- [x] Verify 103 new checks and the expanded 380-check selection.
- [x] Record fifty-two before/after decisions with hands, mana and checked outcomes.
- [x] Finish frontend lint/contracts/build and Chromium with four new human casts.
- [x] Finish full fresh-cache backend suite and repeated seat-balanced replay.
- [x] Refresh Graphify, verify archives, publish and clean closed owned scratch.

Fifty-two actual decisions improve from zero to fifty-two intended checked
outcomes. These controlled public-state scenarios are not deck win percentages
or statistical proof of expert play. Traces retain actions/reasons, hand/cost
data, public combatants/stack and final zones/life.

Development failures are distinct from acceptance. Six hostile-stack fixtures
initially passed both players before announcing the spell, correctly advancing
combat and emptying mana; announcement now retains attacking-seat priority.
Replacement projections are conservative instead of silently selecting an
ordering. A transient fixture stat mutation was replaced with the actual
canonical creature before final source capture. No production deck/card/rule
value was modified to force balance.

Final-source acceptance passes 5,508 backend tests (547 deprecation warnings,
1,022.15 seconds), frontend lint/runtime contracts/production build, the complete
Chromium harness and twelve seat-balanced Tempo/Dimir Control/Tokens/Ramp BO1
samples, repeated twice each (418.721 seconds). No replay anomaly, timeout or
determinism failure is reported. Backend source byte parity is verified across
the full-suite, matrix and retained browser checkouts. Both live local services
return HTTP 200; that is not an HTTPS/LAN deployment or visual-layout audit.

Failures, canonical inputs, before/after traces, source and browser/test evidence
are checksum-verified under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ai-defense/20261004T015103Z/`.
Publication and cleanup receipts accompany the archive. The preceding devotion
milestone holds the consistent private live-database backup; SQLite never runs
on NFS. The user's untracked coder plan is preserved and remains unstaged.

## Known Limitations and Next Upgrades

Unannounced responses remain conditional uncertainty, not clairvoyant knowledge.
This is bounded postcombat resource comparison, not complete future-turn,
end-step-deferral or adversarial search. Life/hand weights are heuristic, not
tournament-calibrated. Unknown choices, larger boards and multitarget/multiaction
lines need further planning. The normal planner on unknown/exhausted projections
is not certified optimal. Arbitrary-card rules, expert any-deck AI, network
release gates and the deferred alpha UI redesign remain open.
