# Shared Counter Entry Routes

## Implemented Scope

The shared entry-counter preparer now covers normal permanent spells, created
tokens (including Incubators and supported creature copies), resolving permanent
spell copies, the two graveyard-return handlers, supported library-search/top-card
battlefield selections and green-creature hand placement.

Existing cards stay in their source zone until all counter/chapter choices finish.
Uncreated token candidates are serialized in the pending packet, not inserted
into game zones or battlefield lists. Every member of a supported simultaneous
batch is prepared before any commit. Intrinsic loyalty/lore, Read Ahead and
supported counter modifications share the same physical placement contract.
Creature returns now emit their own entry event as well as permanent returns.

Non-cast entries do not consume the existing next-cast-creature record and do not
inherit the source effect's announced X, escape or Phyrexian life-payment choices.
Copied spells retain their own copied X but were not cast: compleated does not
reduce their loyalty just because the original used life. Copy entry creates no
token-creation event. These boundaries follow [Wizards rules 111.13, 107.3,
122.6 and 702.150](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.pdf).

Supported standalone, commuting token-creation doubling clauses modify group
size separately from entry counters, once per creation event. Controller-scoped
and global wording are supported. A creation-doubled group can then have each
member's entry counters modified; permanent-spell copy entry is not doubled as
token creation. Non-doubling and conditional token replacement families remain
unfinished.

## Resolution and Continuation

The common stack resolver stages triggers through the entire resolving effect
sequence and its durable choices. Later effects finish before state-based checks
and publication of staged triggers. New continuation-controller metadata preserves
the original caster across nested affected-player choices; a gifted token's
controller does not take over a later life-gain effect. See [rules 704.3-704.4 and
603.3](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.pdf).

This also makes direct stack-resolution helpers perform their completion-time
state-based checks consistently. Existing regressions now expect lethal creatures
in the graveyard and departed tokens ceased at that boundary, rather than requiring
a separate manual SBA call. Divided-damage coverage captures the first SBA
boundary and requires both damage shares to have been applied beforehand.

## Verification

- Eighteen new entry-route cases pass. The focused final set passes 72 checks.
  Seven earlier suite assertions exposed changed helper timing or the previously
  omitted token-count doubling; they now assert the correct completion boundary.
  The divided-damage regression captures the first SBA call and verifies both
  shares were already applied, rather than merely checking final graveyards.
- The isolated full backend suite passes 2,414 tests (229 warnings, 252.83 s).
  Test/API writes use disposable data, never the live database.
- Frontend lint, unit contracts and TypeScript/Vite build pass. Full Chromium
  passes, including the new seat-two token batch: no Incubator exists after the
  first counter choice; both appear with eight counters after the second choice.
  Existing hybrid/compleated casts, recovery/restart, simulator preflight,
  sideboarding and natural human/AI BO3 flows remain passing.
- Eight seeded seat-paired games repeat complete results/logs across sixteen
  executions without timeout. This is smoke repeatability, not statistical
  matchup balance or professional-AI evidence.
- Graphify AST refresh passes: 7,484 nodes, 18,717 edges, 336 communities.
  Modified backend files and new fixtures match the tested copy byte-for-byte.
Three canonical entry-observer fixtures were exported through a read-only
connection to local card knowledge with Scryfall IDs and bulk provenance.
Core-operation packets in tests are explicitly labeled, not invented card text.
Evidence is retained on RCHFiles under project diagnostics `entry-routes/`.

## Known Limitations and Next Upgrades

Supported linked-exile returns now share preparation; see
[linked return scope](linked-entry-counters.md). Special opening entries, exile-and-return-transformed and
other unusual entry routes still need packet integration. General projected
continuous/copy characteristics, simultaneous multi-kind replacement ordering,
arbitrary intrinsic entry clauses, cast-linked one-shot expiry semantics and
conditional/non-doubling token replacements remain unfinished. Phasing, arbitrary
Saga chapters, gained/suppressed abilities and nonlinear AI counter/chapter
valuation remain open. Small deterministic replays do not certify universal
rules, statistical balance or professional-player AI.
