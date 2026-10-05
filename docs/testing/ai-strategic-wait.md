# Strategic Waiting and Public Stack Threats

## Implemented boundaries

The complex-board planner retains its highest-scoring legal action, including a
pass. It no longer substitutes an inferior proactive line merely because waiting
won. A legal pass is included alongside the bounded root shortlist even when
shallow ranking omits it. The same inclusion applies to recursive strategic
nodes and stack-reply shortlists, so candidates can reach actual resolution
rather than being compared only while waiting on the stack.
This is not an instruction to always wait or a change
to game progression, costs, card definitions or matchup win rates.

For counterable opposing stack items, threat ranking compares checked-engine
unanswered resolution with prevention of that item. It accounts for the permanent
actually lost, existing counters, fizzling targets and known terminal outcomes.
Spell, activated and triggered stack kinds use their corresponding counter
handlers; preventing an ability does not remove its source permanent.
The choice-free baseline is reused inside the exact decision scope. Required
choices and changed libraries/opposing hands remain unknown; ordinary heuristic
ranking is retained in those cases. Uncounterable spells retain their danger
score rather than being labeled harmless because a counter cannot prevent them.
This forecast is a threat estimate, not a paid counter action or a prediction of
unseen opponent responses; legal target admission and checked payment still apply.

## Focused evidence

- 433 isolated focused checks pass, including information boundaries, search
  perspective/prefix reuse, removal/counterability and recurring engines.
- 62 new selection checks cover both seats and fourteen style labels, preserving
  better casts as well as better waits. Those labels exercise shared selector
  policy, not measured strategic proficiency in fourteen archetypes.
- Canonical Memnite and The Meathook Massacre fixtures supply completed removal
  utility for controlled selector tests. Their ranking/scoring stubs are explicit;
  these do not establish that the production AI often cast harmful friendly removal.
- Nine new forecast checks cover artifact, enchantment and creature loss, fizzling,
  counterability admission, unknown choices, snapshot parity and source purity.
- Two older fixtures were invalid: one referenced nonexistent removal targets and
  omitted announced-target metadata; another advertised casting without valid mana
  bookkeeping. They now use canonical targets and a paid Torrential Gearhulk line.
  Counter-war, distinct-target and actual casting assertions remain intact.

Development failures are preserved. The first broad candidate also flattened
protected-spell threat; its counterability regression caught that error. Those
partial broad runs were deliberately superseded, not counted as acceptance.
The corrected second candidate passed 7,425 isolated backend tests. Its browser
gate did not pass: natural AI BO3 exceeded the bounded action budget in game
three, turn seventeen. The retained position exposed playable burn and a creature
being held against an empty creature board. That failure motivated deeper-node
pass inclusion, rather than an increased timeout or a forced winner.

The third candidate adds thirteen checks for priority shortlists, actual payable
clear-board hands at Strong/Master for both seats and Burn/Aggro labels, and
single-alternative targeting. All thirteen and the combined 256-check focused
gate pass. A single-alternative spell no longer gains a second planeswalker
target after a player was chosen. Candidate three's browser run again stops at
the total 1,500-action BO3 budget, but its retained state is now different: the
opponent is at two life and Lava Spike is ready. With the persisted Master/Burn
controller identities, offline continuation finishes legally in seven more
actions, including Skullcrack in response. The browser contract now budgets
3,000 priority actions across the whole BO3 and emits bounded progress; it still
requires natural completion and a two-win score. This is a disclosed harness
change, not a forced winner or evidence that the former planning failure did
not exist.

Candidate four also repairs the spell-versus-ability forecast dispatch found
during review. Eight canonical Nissa/Blood Artist prevention and protected-runtime
admission regressions fail under candidate three and pass after the correction.
The combined 121-check forecast/counterability/selection gate passes. Full
isolated backend suite passes all 7,467 tests, with complete test-file discovery
checked across four independent database shards. Frontend tests, lint and build
pass. The full browser gate passes, including naturally completed AI, human/AI
and two-human BO3 sessions; the AI series finishes at batch 51, game three,
turn seventeen, score 2-1. The six-style matrix completes fifteen pairs, thirty
logical games and sixty repeated executions. Complete repeated packets are equal,
with 41,070 decision traces and no reported drift, anomaly or timeout. Separate
strict action reconstruction matches twenty-nine games and rejects one Searing
Blaze cast with no creature target at decision 113. The coupled-target contract
remains open. These checks do not certify optimal play or unrestricted legality.

The same retained browser snapshot was independently restored under candidates
two and three, with only the step moved to precombat main and the active seat
given priority. Both Strong labels already choose checked payable casts. Both
Master labels previously pass; with candidate three, both select a checked
payable Rift Bolt. The authoritative source snapshot remains unchanged in all
eight probes. This is a concrete local decision improvement, not proof that the
entire BO3 or every late-game board is repaired.

## Recorded decision review

The initial permissive action-only reconstruction matches all thirty original
logical samples, complete events and logs, and 18,117 decisions. It does not
establish strict action legality: the subsequently implemented rejecting
diagnostic matches twenty-six and rejects four casts. Every style is included
in the permissive review, with no missed legal land opportunities. Passes with a
legal cast available are:

| Deck | Decisions | Cast-pass opportunities |
| --- | ---: | ---: |
| Blue Control | 3,382 | 59 |
| Ramp | 3,471 | 31 |
| Tempo | 3,201 | 0 |
| Tokens | 2,035 | 8 |
| Mono Red Aggro | 2,835 | 0 |
| Dimir Control | 3,193 | 40 |

All 138 contexts are retained, replacing the earlier first-forty sample bias.
These are review opportunities, not mistakes or evidence of optimal play.
The original matrix is regression data with one seed per pair, not a reliable
win-rate estimate or an expert-player comparison.

The completed candidate-two matrix has fifteen pairs, thirty logical samples
and sixty repeated executions. All complete repeated packets match, containing
44,804 decision traces, with no reported anomalies, timeouts or drift. These are
repeatability results, not a substitute for strict action reconstruction.

## Known Limitations and Next Upgrades

The selected wait still depends on heuristic scores and bounded lookahead. Unknown
replacement/choice continuations retain fallbacks; counter forecasts do not price
every available response or unseen card. Stronger resource planning, uncertain
outcome beliefs, diverse golden decision fixtures, latency and statistical AI
quality evaluation remain open. No cards or deck balance were altered.
