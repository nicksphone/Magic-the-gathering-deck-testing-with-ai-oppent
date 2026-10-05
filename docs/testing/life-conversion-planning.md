# Life Conversion and Public Beneficiary Planning

Status: qualified supported-family milestone. Broader rules and strategic
coverage remain open; see the boundaries below.

## Implemented Families

- Shared life replacement admission and resolution recognize the complete
  unconditional opponent-gain-to-loss clause, including a printed ability-word
  prefix. Canonical Tainted Remedy and Plague Drone use the same handler; there
  is no card-name dispatch. Multiple converters replace one event, not multiply
  its loss. Life gain prohibitions stop the original event; life-total locks
  also prevent its converted loss.
- The affected player chooses between competing gain replacements. Canonical
  Alhammarret's Archive ordering can double the gain before conversion or convert
  first. Snapshot restoration preserves the affected seat and exact source IDs.
  Converted lifelink does not emit a life-gain trigger.
- Supported unconditional own-player loss protection now participates in shared
  state-based checks for life, poison and failed draws. Failed draws protected at
  a check do not remain a permanent future loss flag. Life and poison remain
  current conditions, so removing protection causes a later check to lose.
  Losing printed abilities disables the supported creature static effects.
- Original and copied fixed life instructions use bounded public replacement
  outcomes rather than always favoring their caster. Known conditional branches
  use actual controller land-entry history. Competing replacement ordering is
  valued from the affected player's perspective, including opposing choices.
- Shared pre-selection filtering rejects life-related actions whose checked,
  unanswered public continuation proves a loss, before proactive/anti-stall
  selection can force them. Unknown continuations are retained, not called
  illegal. Damage and caster gain retain their different recipients.

## Evidence and Qualification

The corrected initial canonical engine selection reproduces 11 failures and
eight passes before repair. The first repaired selection finds two remaining
Plague Drone failures: its printed ability-word prefix was not recognized.
After correcting the shared pattern, the frozen overlapping gate passes 147
checks. Subsequent focused coverage, full regression and natural matrix results
must be recorded separately against their exact source snapshots.

New tactical cases exposed both a false Platinum Angel lethal forecast and
suicidal casting through gain conversion. They remain real regressions to close,
not assertions to weaken. Intermediate copy-fixture mistakes used the wrong
option key and method signature; the fixtures now use the actual engine API.
The first combined snapshot passes 429 checks; expanded coverage then reproduces
two suicidal casting failures. The subsequent shared action-selection repair
passes a frozen 479-check overlapping gate. Its cases cover both seats, two
canonical damage/gain spells, four styles and three difficulty settings.
All 616 source/fixture files match the latest frozen candidate. The full 320-file
regression gate passes 7,930 tests in four isolated shards with two workers; those copies
start from a disposable fixture database, not the live database or a claimed
empty-database clean installation.

A subsequent HTTP supplement passes four cases in an empty disposable API
database: both affected seats and both replacement orders, paid canonical casts,
wrong-seat rejection with unchanged snapshots/database, SQLite restoration and
actual spell completion. Its one new test file is outside the earlier frozen
320-file full gate; runtime source is unchanged. Browser and fresh post-fix
match acceptance remain separate.

Later forecast review corrects a draw-score branch that treated winner `0` as a
loss. A separate 213-check frozen selection passes, including actual simultaneous
loss, immutability and the four HTTP cases. This changes one runtime file and one
test file after the 320-file full gate was frozen; that gate cannot certify the
later branch. Require a latest-source follow-up before promoting the candidate.

The subsequent clean committed-source gate includes 321 files/617 source files
and starts without an existing database or ignored developer cache. It is
separate from the earlier 7,930-test fixture-database gate and passes 7,936 tests
at `a9d96ac`, before the later damage timing repair.

The baseline natural matrix uses verified 60-card Boros/Dimir capability decks,
replacing four Grasp of Darkness with four canonical Tainted Remedy. Its frozen
source predates the last suicidal-casting repair. Do not relabel these games as
acceptance of that later edit. Full private traces are retained locally while
running; completed evidence belongs on the verified NFS share.

The baseline completes four logical games/eight repeat executions with zero
reported replay drift. A post-fix matrix runs with byte-identical manifests and
the same seeds/seat schedule, using the later draw-score repair. Strict state
reconstruction and full hand/board decision-context audits are separate checks,
not inferred from a zero-drift counter.

All eight baseline executions now strictly reconstruct, with 2,942 logical
decisions, four actual Tainted Remedy casts and four converted life events.
No gain-spell resolution ended in its controller losing in this small baseline
sample: the suicidal-casting regression is established by canonical unit cases,
not a claimed natural-game improvement.

The post-fix matrix also strictly reconstructs all eight executions and has
2,942 logical decisions, four converter casts and four converted events. Every
retained packet is byte-identical to its baseline counterpart. Thus these games
establish repeatability and exercised conversion, not improved natural decision
quality. The same small sample did not reach the suicidal-casting regressions.

## Resolution Timing Follow-Up

Four canonical cases expose premature lethal creature departure between the
damage and gain instructions of Lightning Helix. Shared damage handling now
retains a lethal creature during staged spell/ability resolution, using the
existing durable resolution/trigger stage. The final state-based check performs
its departure only after the complete instructions finish. No per-card exception
or altered Oracle text is used.

An overlapping frozen 373-check gate passes, including the four timing cases and
four affected-seat replacement-order snapshot cases. Those snapshots preserve
the lethally damaged converter on the battlefield through the pause, then apply
the selected loss amount and finish both spell and creature departures. Initial
fixture failures assumed the wrong printed toughness and the wrong return value
for a paused resolver; corrected fixtures use the canonical three toughness and
the actual pause contract. They are not engine fixes.

This later edit changes the shared damage runtime and one regression file after
the clean 321-file gate was frozen. That older clean gate and the Tainted-only
natural matrix must not certify this timing repair. Require a new exact-source
full gate and creature-source natural/integration acceptance before promotion.
Low-level standalone damage helpers retain their existing completed-event
behavior; shared staged stack resolution is the qualified timing boundary.

An eight-case HTTP supplement now covers both affected seats and both replacement
orders for both an enchantment converter and a lethally damaged creature converter.
Canonical Lightning Helix is paid and cast through HTTP, the damaged Plague Drone
remains active during the choice, wrong-seat submissions leave memory/database
unchanged, and SQLite restoration retains the damage and resolution stage. Choosing
the replacement completes the spell and only then moves the creature to the
graveyard. The first four added cases used a nonexistent damage attribute; the
corrected assertions use the existing marked-damage counter. No runtime repair
was needed for this supplement. These four additional HTTP cases are outside the
frozen full gate at `865a9b4`, whose runtime is unchanged by the supplement.

## Latest Qualification

- The clean timing gate passes 7,944 tests across all 321 discovered files,
  assigned exactly once to four isolated shards. All 617 source/fixture hashes
  match the frozen `865a9b4` source in every shard. Databases are absent at launch.
  Only the four separately passing HTTP cases differ in the later backend source;
  no runtime source moved while this gate ran.
- Frontend tests, lint and production build pass. The full browser gate passes
  including natural BO3 in all three controller modes. Four new browser cases
  cover both seats and both life-replacement orders, reload during the pause,
  marked lethal damage and final spell/creature departure. These are actual UI
  choices, separate from the eight HTTP/SQLite cases.
- Four creature-source capability games retain eight exact repeat packets and
  strictly reconstruct all eight executions, with 2,788 logical decisions.
  Three canonical Plague Drone casts resolve, and the creature actually attacks
  and receives lethal damage. No converted life event occurs in this sample;
  targeted canonical tests, not this matrix, establish conversion timing.
- A held converter is not automatically a missed play. A separate strict
  opportunity audit of the first game finds two legal cast opportunities: land
  play followed by Torrential Gearhulk. This is recorded context, not proof that
  either alternative is optimal.
- Completed source, gates and private decision logs are archived on verified
  mounted NFS. Clean dependency installation, cross-device human acceptance and
  long-session competitive play are not established by these checks.

## Boundaries and Next Gates

- Public life-event planning explores at most sixteen replacement continuations
  with depth eight. Incomplete choices return unknown. It does not settle all
  downstream life-trigger stacks or value every secondary permanent benefit.
- A gain-to-draw replacement returns unknown before drawing; neither hidden card
  identities nor speculative draws may establish a certain outcome.
- Supported loss protection is the verified unconditional own-player clause,
  not a complete implementation of conditional loss protection, all alternate
  wins, game-wide win prohibitions or multiplayer rules. Draw games remain
  distinct from a loss, and existing simultaneous-loss tests must stay green.
- Expand natural samples that actually reach competing conversion effects and
  secondary trigger value. Preserve exact source/seed provenance and private
  decision traces; do not infer semantic coverage from completed game counts.
- Continue broader strategic planning across adverse replacements and competing
  effects; a few deterministic capability games are not expert-player or
  tournament-balance certification.

Canonical raw responses, source URLs and hashes are in
`backend/tests/fixtures/life_conversion/provenance.json`. Rules grounding:
[official September 25 comprehensive rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
especially 101.2 and 704.5a-c. Printed Oracle text remains unchanged.
