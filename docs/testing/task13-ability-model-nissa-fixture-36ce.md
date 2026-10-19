# Task 1.3: canonical Nissa ability-model fixture

Base: `36ce25f52cae12c9f6f0faf9f6b32e4bedb903ab`. This bounded test-only
migration changes only Nissa's positive fixture in `test_ability_model.py`,
with one new fidelity module and this document. It is not repository-wide
Task 1.3 or Phase 1 completion.

The four original test names and all eleven assertion ASTs are unchanged.
The Test Bolt, Unknown Relic and Event Permanent test functions are
byte-identical. Nissa's original state setup, fixed source ID, owner,
controller, hand zone, consumer call and assertions are preserved. The source
remains standalone rather than being inserted into the state's stock/cards.

Nissa now uses the unchanged shared `canonical_positive_fixtures.cached_card`
API: the complete official seed155 object is pinned by
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`,
and the existing normalizer provides its complete cache projection. Printed
types and keywords use the existing mappers. Mana, loyalty, colors, type line,
layout, faces, power/toughness and the entire Oracle body are derived from that
projection, not handwritten substitutes. The shared display-only image
operand is truthy, so normalization creates no placeholder image. No new
helper, RAW data, HTTP request or shared-loader edit is needed.

The new fidelity module calls the actual original Nissa test and captures its
card at the `build_ability_spec` boundary. It checks full Oracle equality,
printed metadata, identity/placement/call shape, independent objects and
unchanged pinned RAW/provenance. This is not a standalone replacement builder
or an ImportError-only RED. The original whole module separately executes its
real parser/ability calls and unchanged assertions.

## Actual qualification

- Original whole module plus fidelity RED: 3 failed, 5 passed, 1.96 s. All
  four original tests passed; the new captures exposed the fabricated Nissa
  Oracle and missing printed metadata.
- Same two whole modules GREEN: 8 passed, 1.88 s.
- Final three whole modules: 21 passed, 2.73 s. The sole existing neighbor is
  `test_canonical_positive_fixture_fidelity.py`. The 8 are included in 21.

Every run used a precollection audit ceiling with seven exercised native
SQLite/socket/child/provider denials, all SQLite aliases denied,
`--noconftest`, no filters, and a 300 s TERM / 15 s KILL outer bound. There
were zero unexpected I/O attempts, no database, no source/media additions,
unchanged existing source and 2,946 retained runtime regular-file hashes,
matching FD sets, no remaining children or extra threads, and disposal of the
unused import-created engine. No production, API, schema, AI policy, parent
worktree, main/index or dependency change was made. No native/browser run or
installation occurred. Independent review is a separate parent-owned step.
