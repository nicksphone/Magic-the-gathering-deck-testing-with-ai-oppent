# Independent Offline Seed Snapshots

**Goal:** Caller edits to returned offline metadata must not change canonical
seed facts, another lookup, another hydrated row or a later match's printed data.

**Observed defect:** `seed_card_payload` returns the shared catalog dictionary.
Hydration shallowly incorporates its nested faces. A returned Brutal Cathar face
edited in one call appears edited in a later independent hydration call.

**Approach:** Deep-copy at the seed lookup boundary for both ordinary/normalized
names and split-name front-face fallback. Preserve every stored field, name
normalization rule and missing-name result. Do not modify the committed seed,
card rules, cached/knowledge precedence, action validation or AI policy. This
does not promise complete isolation of every other mutable gameplay structure.

**Files:** `backend/card_data/seed_cards.py`,
`backend/tests/test_seed_payload_isolation.py`,
`backend/scripts/generate_startup_media_pins.py`,
`backend/tests/test_startup_media_pins.py`, release documentation.

- [x] Add pure regressions for root/nested edits, aliases, repeated hydration and
  later real MatchFactory births/snapshot restoration; observe baseline failures.
- [x] Return independent seed snapshots in both lookup branches.
- [x] Run the whole affected pure hydration/metadata/face cohorts with I/O denied;
  retain any setup/test failures and preserve all source seed bytes.
- [x] Obtain independent code review, document exact scope and commit/export the
  change. Full backend, HTTP/browser, native Forge and RC acceptance remain open.

**Review focus:** Nested face color lists; punctuation aliases and split-name
fallback; multiple rows for one card; callers clearing the whole returned dict;
unchanged missing-name behavior. The public API must keep ordinary mutable dicts
for callers rather than introducing incompatible read-only mappings.

**Compatibility ruling:** The actual startup-media generator expected shared
payload identity. Reproduce that failure, bind the exact new seed source digest
and compare complete typed JSON facts instead. Preserve every other pin and
existing assertion. Actual old/new artifacts must retain all media/structural
facts with only the seed source-module pin differing. Review also required two
mutation controls exercising the real front-fallback branch; both fail when
only that branch's copy is removed. The final pure cohort passes562 across
eleven whole modules; current-source bindings10 pass separately.

**Final evidence:** Independent follow-up review approves with no remaining
findings and reruns the complete isolation/migration/generator subset385. A
separate predeclared same-coordinate Tempo/Tribal Master old/new comparison
completes both games with identical808 raw log lines and346 checked actions;
unchanged source pins and raw receipts are independently verified. This is
one-coordinate component evidence, not strength, BO3 or full RC acceptance.
