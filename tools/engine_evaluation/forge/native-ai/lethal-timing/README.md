# Predicted Lethal Player-Damage Timing

Separate generic increment over pinned Forge
`61e9442c433711a82258daca3236f936a1d6f70e`, tested with the frozen ff89 native
affordability shadow and qualified base `59228745...`. See [NOTICE.md](NOTICE.md).
No upstream source or earlier candidate, diagnostic or quality cohort changes.

## Product Scope

Only `forge-ai/src/main/java/forge/ai/ability/DamageDealAi.java` changes, emitting
only `forge/ai/ability/DamageDealAi.class`. The existing player-target timing
disjunction gains one exception: native predicted positive life damage at least
the opponent's life, when that player can lose life and can lose for zero life.
Native infect-converted damage is conservatively excluded from this life-total
exception; no new poison-lethal policy is introduced.

Ordinary timing conditions remain first and short circuit unchanged. The
existing `shouldTgtP`, target restrictions, prevention/protection, cost,
reservation and own-cast curse checks still apply. No card names, mode IDs,
global `playImmediately` change, policy rewrite, direct RNG calls, counterfactual
cast/evaluator retries or diagnostic code are added to the product.

The exception uses the same native static replacement/prevention forecast as
`DamageAiBase.shouldTgtP`, not raw damage. Because the latter's boolean API
exposes no predicted amount, the newly admitted path performs a native forecast
and then retains the original `shouldTgtP` call with its existing forecast.
There is no duplicate AI choice or affordability query. This is intentionally
not a broad correctness certificate for every replacement or additional cost.

Independent review also identified a conditional limit: native prevention
forecasting can evaluate an authored `Count$Random` amount and thereby consume
native RNG. There are no new direct RNG calls or RNG restoration, but the extra
forecast is not universally RNG-pure, including when it declines the timing
exception. The reported canonical controls do not certify all such expressions.

## Canonical Controls

`NativeLethalTimingControls.java` uses complete canonical native cards, Default
AI and the qualified PublicNameController. All 26 positions are explicitly
constructed, not claimed natural games. `test.sh` checks all 14 full card-program
snapshots against the pinned native files before starting one sandboxed JVM.

Both seats must actually select, pay, put on stack, resolve and receive native
wins for Boros Charm's damage mode, Skullcrack and Goblin Fireslinger's ability.
The two spells pay all three lands, including native Thalia tax; Fireslinger
pays its native tap cost. Winners are awarded by native state-based actions,
not a harness `setWinner` or `setGameOver`.

Final same-harness baseline is 6 expected RED / 20 PASS (both-seat instant,
modal and activated lethals withheld); final candidate is 26 PASS / 0 errors.
Earlier 20-position RED/GREEN and the intermediate infect RED are retained as
historical evidence, not relabelled as final-byte qualifications.

Both seats also check ordinary nonlethal MAIN1 holding, ordinary nonlethal
opponent-end-step casting/resolution, partial/full prevention, hexproof,
tax-unpayable mana, Platinum Angel, Phyrexian Unlife, own Eidolon backlash and
Phyresis-converted poison damage. The infect case caught an intermediate
over-broad exception (2 RED / 24 PASS) before the final native conversion guard.

## Reproduction

These commands require the existing qualified local build, ff89 shadow and
original closed case00. They add no dependencies, SQL or network access. All
engine invocations must be sequential, never concurrent. Outputs must be fresh
absolute local directories, never NFS runtime directories.

```bash
bash build.sh "$BASE_IDENTITY" "$NEW_BUILD"
bash test.sh "$BASE_IDENTITY" "$FF89/shadow" "$RED"
bash test.sh "$BASE_IDENTITY" "$NEW_BUILD/shadow:$FF89/shadow" "$GREEN"
python3 natural-case00.py "$ORIGINAL_CASE00" "$SCRATCH/natural-baseline"
python3 natural-case00.py "$ORIGINAL_CASE00" "$SCRATCH/natural-final" "$NEW_BUILD/shadow"
```

`build.sh` pins the base identity and original whole-source hash, applies the
patch with zero fuzz to a new private copy, restricts emitted payloads, records
source/class/compiler/input hashes and derives a path-independent content ID.
An independent local rebuild reproduced final source, class and content ID.
No profile is built or published here; parent composition/allowlisting is separate.

`natural-case00.py` reuses the original compiled NativeNameMatchProbe and exact
spec, decks, seed, Default/PublicName/ff89 classpath, processor/heap/clock limits
and isolated launch. Original inputs are mounted read-only. Candidate runs only
prepend the single new class. Results require exit 0 plus native completed
series events; no outcomes are forced. `verify-closed.py` is offline evidence
verification for the retained named scratch layout, not a new game runner.

## Bounded Natural Evidence

Fresh baseline reproduces original Burn losses on native turns 19 and 20.
Final candidate naturally wins both games on native turns 16 and 12. Game0
matches baseline for exactly 360 log rows and 348 actor observations before
casting the same Charm card28 earlier, in turn16 upkeep: native Plateau/Plains
mana entries, cast, four damage, White life 4 to 0, resolution and native win.
The original turn18 position is never reached; this is not represented as an
identical-position turn18 replay. Snapshot records lack mana-pool/log-index
fields; payment comes from the native log sequence, not invented alignment.

Final source SHA256:
`53e892f046cad6b62ce709dd6a788f04cb13f9195672b38cba8759454c23d3df`

Final class SHA256:
`50a0d76548c8a53b1b90d7d51105ffcf9e01559526a934b853a63733486218a6`

This result is one declared natural series and controlled regression coverage,
not self-play win-rate evidence, coupled app qualification, save compatibility,
all-cost fairness or a published runtime profile. Existing parent tests and
other workers' sources are untouched. Full native initialization warnings are
retained in private logs rather than hidden or treated as harness errors.
