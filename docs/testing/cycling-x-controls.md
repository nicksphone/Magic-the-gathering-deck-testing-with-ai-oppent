# Cycling X Controls

This narrow frontend patch is based on the frozen source-only candidate
`/home/nick/.hermes/cache/scratch/mtg-composed-release-xxWjrw`, not an engine
patch applied to the earlier `3ccbdf2` audit. No parent/main/backend edits.

Both castable and cycling-only hand branches use one control. Its options are
exactly the current actor's offered cycling moves, including offered zero. The
selected move determines both displayed cost and unchanged `cycle_card`
`x_value`. A previous selection no longer offered is replaced by the first
currently offered move; no mana estimate, resource selection, or invented X
bound is used. Fixed-cost cycling remains a button without an X selector.

## Qualification

- New component render check: 16 cases, both seats/branches, offered `[0]`,
  `[0,1,2]`, `[2]`, fixed-cost Renewed Faith, absent cycling move, private hand.
  These are consumer rendering bounds, not new engine affordability claims.
- Unchanged human-flow16 actual-App/real checked HTTP sidecar: 198 PASS and
  10 RED assertions, 41.924 seconds, strict exit 1. All Shark explicit X=2
  actions/payments/self-cycling tokens pass in both seats. Renewed actual
  optional Apply/Decline choices, choice ownership/privacy and once-only draw
  pass. Real stale action after backend restart is rejected with 409 without a
  second mutation. Refresh/root purity/private hand checks pass.
- Remaining frozen-engine gaps: normal Renewed cast gains eight rather than
  six life; selected Tower sacrifice loses Hangarback's two counters in death
  LKI and produces no tokens. Consequently token count/type/effective-view
  assertions remain RED in both seats. No backend repair or test weakening.
- Existing frontend lint, build and contract/unit command pass. No full shared
  browser gate or family/variant certification.

Run from a checkout with external dependencies:

```sh
cd frontend
node tests/cycling-x-controls.mjs
npm run lint
npm run build
npm run test:unit
cd ..
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/path/to/external/frontend/node_modules \
node frontend/tests/browser-human-flow-audit.mjs
```

The unchanged audit is a separate tests-only dependency, SHA256
`d8a37ac75955a8da498ace00aecb0ac4124898afd039b2c4e4f2c1e59676ca61`,
archived under `human-flow-audit/mtg-human-flow-audit-aKT3gi`. It contributes
the immutable canonical fixture used by the new render check. Apply that audit
once for qualification; it adds no product backend code.

Canonical Shark/Renewed/Hangarback facts and explicit diagnostic positions are
unchanged. This does not claim Krosan Tusker's additional compound clauses,
natural historical games, every cycling variant, AI policy or correct missing
engine token semantics. Public choice ownership is tested separately from the
client's both-human match envelope; hidden library order is never a policy
input. Verified private NFS evidence contains exact source and raw failures.
