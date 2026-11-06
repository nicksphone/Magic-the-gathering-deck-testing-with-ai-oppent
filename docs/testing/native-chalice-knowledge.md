# Native Chalice Knowledge Correction

This modifies Forge Team/Card-Forge `PermanentAi` at upstream revision
`61e9442c433711a82258daca3236f936a1d6f70e`. The
[credited source family](../../tools/engine_evaluation/forge/native-ai/chalice-knowledge/README.md)
retains the complete pre/postimage, GPL-3.0-or-later license, patch and canonical
programs. It is not a newly trained model or a rules engine built from scratch.

## Defect And Correction

The original Chalice heuristic counted physical opponent cards with a predicate
that excluded the hand. Both seats chose differently after an unseen Opt/Bear
hand/library swap despite identical actor input, disclosed registration and full
incoming RNG state. It also counted a spent public Opt, but stopped counting that
Opt after a known native return to hand.

The correction starts from disclosed registered quantities and subtracts only
observer-identifiable spent originals. Hand/library contents are not scanned.
Both native CardView identity permissions precede inspection of public-zone
cards. Unknown face-down identities, ambiguous native copies and noncollectible
objects cannot silently debit a particular registered card. Non-Main copies
reserve quantities first. Known potential recasting, including genuine
Breach-granted Escape, remains in the possible future pool.

This retains an explicit disclosed-deck premise. It is not permission to inspect
a closed decklist. Unresolved public permission conditions and provenance are
handled conservatively; this can overestimate possible future casts. Alternate
faces, all conjured threats, every recast mechanism and unique physical origin
are not fully forecast. Existing phase/cost checks, Chalice thresholds and other
upstream policy branches remain unchanged.

## Executed Checks

- Baseline: eight original first-choice rows exposed two private-pair failures;
  two Telepathy visibility contrasts were valid. Ten additional goldens had six
  passes/four strict failures, with no harness or control errors. The opaque
  exile comparisons and real Escape controls already passed.
- Corrected composition: the same eight rows satisfy both private comparisons;
  all ten additional goldens pass, including both opaque-exile pairs. Native
  exit zero in 12.922 seconds. These are controlled cases and pair assertions,
  not eighteen games or TestNG methods.
- A separate fresh JVM ran the unchanged original eight-case main successfully
  in 10.842 seconds. It is not added to the eighteen-case cohort.
- Independent preservation: sixteen existing Fog cases, two privacy pairs and
  eight full-row comparisons pass, including 32 serialized-RNG field comparisons.
  The retained baseline was not rerun; source/payload bytes remained unchanged.
- The published portable runner independently passed the same eighteen-case
  contracts: native exit zero in 11.242 seconds, 20.199 seconds including intake
  and compilation. All 59,971 declared native resource files matched before/end.
  Its namespace controls do not imply the private JNI SQL guard was installed.
- All 28 synthetic profile checks pass; all 26 prior test bodies are unchanged.
  Schema 7 requires exactly nine sources/sixteen classes, preserving every prior
  payload and adding only `PermanentAi`. Partial/extra sets and changed bytes
  reject. Native class bytes were independently compiled.

The original audit and golden Java sources are unchanged. New goldens explicitly
mark trusted registered-original construction as the native match producer does;
the old audit was not retroactively upgraded. No seed search, late RNG reset,
forced cast/X, changed expectation or forced winner was used.

## Fresh Built-UI Integration

One predeclared Dimir Control/Ramp game completed naturally on turn 35 with
439 rendered human-side answers and 439 matching native starts/returns, in
241.479 seconds. The human Ramp picker is unchanged and is not expert play.
No exact turn or winner was required. This reused the retained private seed,
not a reference replay or a seed search.

All sixteen actual override origins matched the new prefix. All nine sources,
sixteen class files, 59,971 native resources, 4,799 clean-app source files and
cached Node dependencies remained unchanged. Reload/capability/stale/duplicate
controls passed. The game checked 2,577 actor snapshots and 2,369 ordinary opaque
opponent-hand responses; explicit reveal episodes were zero and are not positive
reveal qualification. All 23 observed owned processes ended, accessible owned
handles were absent, external fuser was empty and the closed local database
passed integrity checking. Unrelated process-visibility limits remain recorded.

Private hands, RNG streams, seed, browser evidence and database copies are
archived privately on verified NFS, never published as fixtures. The protected
owner-lock body was excluded without reading, hashing or copying it.

The distinct profile build is
`2975f9bdf6f3f7c64c2ed0f5abc677434f2bef419ccfcdcda45179ff0b17faea`;
composition is
`a7d94a7e8998cdc81fb6f6cc762a551e1e03f1c918f0e9fbbea56155b6ef32c1`.
The game checks app integration, not whether this matchup naturally exercised
Chalice or every Fog interaction. No live-default switch, general AI fairness,
playing-strength, durable-save, best-of-three or overall RC acceptance is claimed.
