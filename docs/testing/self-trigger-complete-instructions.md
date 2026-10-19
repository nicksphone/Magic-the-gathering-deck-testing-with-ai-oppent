# Complete Self-Trigger Instructions

## Immutable Base And Scope

Source is an actual Git archive of commit `c16ea8dde513c32477f8463e2a008f518d6fa4b7`,
tree `14ce4fd758d5605a833cfb8abca5d90ad8f5f1de`, archive SHA256
`7b04dc54549229c28b60393e3d04271afbf508d881d0c9f1580ac9404fd72bef`.
The remote immutable commit was fetched into an owned disposable bare repository;
no moving parent/main source or database was copied. Source has no `.git`, uses
an explicit isolated-source marker and fresh local SQLite, and runs with the
declared qualified Python 3.12.3 environment. Original audit dependency:
`trigger-instruction-compilation-audit-LAdBvp/integration.patch`, SHA256
`2210c8d5c01cd917c3af231170935e372d87b3cb2fb064794a8a79fb29c7fb51`.

Only two production files change:

| File | Preimage | Postimage |
| --- | --- | --- |
| `rules_engine/events.py` | `890f0d1d23d62a17607f7437f302a0a4216fd1a49eacbcc6599dda5673a638e3` | `06f444e03c8fbee15b87e16d0afa2848a7af3d71c1daefa18e2511c36294ab66` |
| `rules_engine/oracle_effects.py` | `87eff1e4cf87f0d20c8329e0f56debdd517f31ac81acb0902e8107f03926c9a5` | `9e7fc3a319a3d0be5c6cfde86db345630334f7c8dd64a9371dd5ad123aef2419` |

The added pure compiler fully matches a draw instruction, or unconditional
numeric life gain followed by draw, using existing `DRAW_RE`, `GAIN_RE`,
`_parse_count_token` and ordered `effect_sequence`. The existing count parser,
constants, generic substring parser, activated regex/extractor and every old
oracle module AST node remain unchanged. No new card-name reward branch exists.

Event admission uses the actual matched self-cast clause/current source identity,
or an exact ordinary self-entry clause. It runs after existing dedicated handlers
and before legacy substring rewards. Existing flashback, kicker, next-turn draw,
entry/transform and other dedicated routes remain intact. Unmatched complete
bodies get `__unsupported_trigger_instruction` and a logged diagnostic, not a
partial draw/life reward. The observer allowlist is unchanged and is not the
causal Cloudblazer path. Original event statements remain AST-identical after
removing the three additive admission statements; all other event AST is equal.

## Ordinary Qualification

- Original 60 audit assertions UNCHANGED: 60 PASS / 410 warnings / 28.62s / exit 0.
- Original 60 plus NEW 59: 119 PASS / 674 warnings / 35.09s / exit 0.
- Eight whole ORIGINAL neighbors: 161 PASS / one stale ordering assertion FAIL /
  103 warnings / 158.84s / exit 1, preserved separately.
- Final twelve whole modules, including separately adapted ordering test:
  **281 PASS / 712 warnings / 168.03s / exit 0**.

Every gate has an explicit 900-second bound. No exclusions, skips, expected
failures, monkeypatched outcomes, fabricated triggers/stack items or rewritten
canonical Oracle were used. Observational wrappers call the original compiler.
Network and foreign SQLite connections are forbidden by the audit hook.

Both seats actually pay for and cast full canonical Kozilek and Cloudblazer,
then respond and resolve genuine triggers. Exact draw-four and life-two/draw-two,
Thought Reflection draw replacement, Stifle responses, actor-private views,
snapshot subprocess round trips and HTTP cold restores are included. The NEW
controls exercise pure grammar boundaries, zero/integer/number-word draw counts,
no partial reward for a genuine Riverwise Augur unsupported suffix, deck-out after
correctly ordered life gain, and deliberate Stinkweed Imp dredge plus remaining
draw continuation without replaying life gain. Eight memory/file HTTP dredge
cases prove wrong-actor 422 full-root/controller/SQL invariance. Four HTTP Augur
cases preserve explicit unsupported receipts without granting a prefix reward.

Private memory is qualified precisely: an Imp publicly moved from graveyard to
hand remains known in `decision_view`; other drawn hand cards and all hidden
library cards remain unknown. This is not a blanket claim of sandbox GET secrecy.

The draft NEW 58 ledger remains 48 PASS / 10 fixture FAIL / 38.50s / exit 1:
two fixtures lacked human trigger-target policy and eight used an inappropriate
blanket hidden-hand helper after publicly witnessed dredge. Only NEW fixture
policy/privacy code was repaired; immutable original 60 and audit archive bytes
remain unchanged. A malformed `you gains` grammar negative was then added.

## Separate Ordering Adaptation

The old Ulamog counter test resolves only one top item after countering its source.
Real graveyard entry adds a graveyard-shuffle trigger above the independently
retained cast destruction trigger. NEW full canonical Ulamog + paid Counterspell
episodes on BOTH seats prove the actual order and final chosen Copter destruction;
Kozilek + Counterspell likewise still draws four after its graveyard shuffle.

`cast-counter-order-test-adaptation.patch` ONLY adds assertions for shuffle on top,
target still on battlefield after that resolution, retained destruction next,
and the second resolution. All existing graveyard-source/destruction/other-target
assertions and all other tests remain. Original preimage SHA256
`3521d8458c874e11dd8111dfbe8b3ebe5b7e63ba0227e37a94d8cc4eeee70008`;
adapted postimage `28e550db89bbd5d42cdac836fd1ea9d61a0ac4e0a0e02176051ee85659b2d8f8`.
The original failure ledgers are not renamed green or erased.

## Artifacts And Boundaries

Apply the immutable original audit dependency once, then this `integration.patch`
(cumulative two production paths + NEW tests/fixtures/document), and the separate
ordering adaptation when qualifying the final twelve modules. `production.patch`
is the two production paths only; do not double-apply it with integration.patch.
No whole-file overlays are needed. Jason's activated regex/extraction changes
are separately owned disjoint hunks; this gate did not consume or certify them.

Five NEW unchanged complete Scryfall API responses plus provenance support the
counter/continuation/unsupported controls. Grammar-unit strings are parser
contracts, not Oracle assigned to fictional cards. Canonical retained mana pools,
graveyard/battlefield positions and human-choice policy are explicit fixtures,
not natural full-deck/BO3/autoplay qualification.

Only numeral life gain and supported integer/number-word draw counts are admitted
by the new body grammar. Targeted draw, X, reversed compounds, arbitrary suffixes,
conditionals, optional payments and unresolved card choices are not admitted by
this helper. Existing dedicated handlers are not blanket-demoted. Riverwise's
creature cast/entry can still return HTTP 200 with an explicit unsupported trigger;
that is NOT complete Riverwise instruction support or a new raw API admission gate.
General multiple self-trigger clauses, broad entry/transform compounds, optional
land-from-hand/Growth Spiral/Grazer, paid optional continuations, draw-redirection
such as Notion Thief, interacting dredge/mill batches, legend/SBA, AI, GUI and
whole-release readiness remain outside this product certificate.
