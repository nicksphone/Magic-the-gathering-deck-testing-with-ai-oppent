# Known Held-Piece Increment

## Scope And Remedy

One incremental correction against exact E/final content
`ff89fd32da4e011d9e8f9af613a07a484894171ba7e4045c3932fcfaed4de398`.
The only changed native source is
`forge-ai/src/main/java/forge/ai/ComputerUtilMana.java`.
No upstream, Q, E, prior candidate, earlier test, profile, app or graph is edited.
The patch retains the parent's earlier Fog/source/empty-source corrections.

`canPayShardWithSpellAbility(..., Predicate<Card> knownCard)` now calls a private
`holdsKnownKillPiece(Player, Predicate<Card>)` for its discard-cost strategic veto.
The private helper implements precisely the native `ComboPlan.holdsKillPiece`
per-card condition using the existing public `isStormFinisher(Card)` and
`isRecursionAbility(Collection<SpellAbility>)` helpers. Crucially, the supplied
knowledge predicate runs **before** any type, keyword, role/name or ability
inspection of a hand card. Unknown identities cannot drive this held-piece veto.
The actual hand is not replaced, inferred, mutated or passed as a fictional hand.

For `knownCard == null`, the helper delegates directly to the original
`ComboPlan.holdsKillPiece(Player)`. Unrestricted owner paths therefore preserve
the original policy, including its existing any-CostDiscard (not solely discard
the whole hand) behavior. Known/public/legitimately remembered held pieces still
drive the native heuristic. The fix neither disables the opponent-Fog heuristic
nor inserts any card name, new public API, solver, rule, or production file.
Unmodified `ComboPlan.java:2472,2481,2545` supplies the original semantic policy.

The baseline source is E/final/**source**, not an assumed `src` directory.
`known-held-piece.patch` includes GPL attribution and the exact preimage hash.
See [NOTICE.md](NOTICE.md) and the unchanged full canonical card programs and
provenance in [../NOTICE.md](../NOTICE.md).

## Observed Results

| Unchanged Checks | Baseline E | New Candidate |
| --- | --- | --- |
| NativeAdditionalCostFollowup, six checks | 2 RED / 4 PASS / 0 errors | 0 RED / 6 PASS / 0 errors |
| NativeFogBoundaryRegression | Not rerun this increment on E | 8 PASS |
| NativeFogKnowledgeControls | Not rerun this increment on E | 12 PASS |
| NativeHiddenManaFollowup | Not rerun this increment on E | 6 PASS |
| NativeKnownManaControls | Not rerun this increment on E | 4 PASS |
| New native owner held-piece parity, both seats | 2 PASS | 2 PASS |

Candidate total: **38 PASS / 0 RED / 0 errors**. The requested original 30
ordinary checks and held-piece six have no assertion or source changes.
All archived historical source pins and the original follow-up's eleven file
pins pass before/end. Each held-piece run completes twelve actual native attack
callbacks. Both strict pairs retain equal actor views, native callback knowledge,
pre-decision RNG, actual decisions, affordability and ending RNG after the fix.
The two independent legitimate-knowledge controls and two public-mana controls
remain ordinary PASS. No generated private row or RNG digest is published here.

The new owner control uses three real native poses per seat: the original held-
piece veto, ordinary hand, and independent public funding. It checks the legacy
three-argument cost API, explicit-null scoped cost API, all-known scoped cost API,
and `hasAFogEffect(owner, owner, false)`. The complete six JSON observation receipts,
including owner view and incoming/ending RNG, are **byte-identical** across E and
the new candidate. These are affordability probes, not new full games or a claim
to execute a discard payment; the unchanged original owner-payment tests also pass.

One malformed patch-header attempt stopped before compilation. One new-control
compile attempt stopped before a native callback because its compile CP omitted
the scoped overload-bearing shadow. Both attempts are archived, not counted as
engine RED. The production condition and old tests were not weakened. The final
runner prepends the tested shadow at compile and runtime, appending test-only
classes to the exact ordered qualified base CP.

## Frozen Candidate And Pins

Local retained candidate:
`/home/nick/.hermes/cache/scratch/mtg-jev-ui-clarity-20261025-krVbf5Hv/native-held-piece-20261106-ePpUn2Iz/candidate`.

Content identity:
`75d4ac3971e7f970d2e3c62ba12f25aba639eba5fd36d0ed2f930a4ea17511b7`.
This is SHA-256 of canonical `jq -Sc` IDENTITY.json including its trailing newline.
[FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json) carries exact source pre/post hashes,
all four emitted payloads, local paths, manifest hashes and the required base pin.
The local candidate also retains full source, the patch, license, notices,
compile command and manifest. It is not an app/runtime profile publication.

| Artifact | SHA-256 |
| --- | --- |
| Incremental patch | `cc1468a4a764e95764880a6397dac7210e87cc2a315c4cde2e195b867c7e3669` |
| Mana source preimage | `6928620486da73f525fc5eb5e9369d47a2ceeb444706f4711da173e481948c54` |
| Mana source postimage | `11c9378f3f0003c7e4a83eb0c3fc1aa6000e5d566c11897a9d700da02c14d04b` |
| ComputerUtil.class | `23b15557de80e398db989e40d78bb6b1849ba19f91a98f7419fb16f44ca65a0a` |
| ComputerUtilCost$1.class | `05b1ab83a06f559594b8cca98d748ce23da7e4e3b6840aeb7b372c237fda6732` |
| ComputerUtilCost.class | `a5825608bc38f757af2341cf4af081f5bb58288e56958689ccc670c7a4124e29` |
| ComputerUtilMana.class | `42172f585bd4b62d8b53dda34a693736fadfdbbf8413cfdb7943c6fb1eb8cdac` |
| MANIFEST.json | `ee5c65cfdcd79309ed6ff79759fef41c48680dc1285bb5d44683b1d83aca3519` |
| IDENTITY.json | `cc99465265b8159dcbb55d95301319d42c00cedd26784e50234483883b33f5a5` |
| Ordered base compiler CP file | `9c6624690329d60fc4e3c16847056c6811c92707c93872d3bfe36ee2faa78c33` |
| Actual candidate runtime CP file | `405522f811b2e521ee0ccdd8123a57c8c0f1f7498c4f08f6b5c9d7dda4a15dc8` |

The first three payloads and their two source files are byte-identical to E.
Exactly four class files are emitted, including Cost$1; no implicit compilation
or fourth production source is admitted. The unchanged native ComboPlan class
hash is `99ea60bfe13a148635a0067480d0ef57cf04ce8ce4a06dc4f6b044d28d0610e8`.
The held-piece harness verifies seventeen explicit loaded resources before/end.
All four candidate resource origins and hashes match the manifest, rather than
an E/Q/old-shadow fallback. Every suite's origin list is unchanged before/end.

Exact Temurin 21.0.13+9 and ordered 102-entry CP come only from Q's unchanged
BUILD-IDENTITY.json. Base build remains
`59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605`,
required base launch SHA remains
`ee58d6110017448391e210c1722d6f1450904c239cc297282f34e4ed4c588562`.
Explicit `--release 17 -implicit:none` compiles only the three named source files.
One own JVM runs at a time: nice 10, heap 768 MiB, metaspace 192 MiB, one active
processor, Serial GC, a 180-second wall limit, isolated PID/network namespace,
read-only engine/Q/shadow mounts and fresh writable local test home/tmp.
Every executed runtime network trace has zero IP connects and zero non-netlink
sends, with three IP socket creations. This is not a zero-attempted-IO claim.

## Reproduce

```sh
FIX=tools/engine_evaluation/forge/ai-boundary/additional-cost-followup/held-piece-fix
E=$(cat "$U/CURRENT-FORGE-EMPTY-SOURCE.path")
Q="$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json"
bash "$FIX/build.sh" "$Q" "$E/final" /new/local/candidate
bash "$FIX/run-tests.sh" "$Q" /new/local/candidate /new/local/results
```

The unchanged baseline launcher is `../run.sh`; exit 1 is its two genuine REDs.
The new owner control also runs against unchanged E by passing `"$E/final"` to
the new runner and selecting `NativeHeldPieceOwnerControls`. All canonical source
files are byte-compared against pinned Forge before offline tests. No network,
dependency installation, SQL, models, secrets or TypeSafe is used.

## Evidence And Limits

Private archive directory:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/native-held-piece-20261106-ePpUn2Iz/`.
It contains all attempts, source/canonical copies, exact argv/CP, hashes, views,
actual decisions, RNG-state receipts and trace files. `VERIFIED.json` records
mounted-writable NFS and full archive readback byte comparison before disposable
scratch cleanup. The qualified local candidate is retained for the parent.

This closes the reproduced held-piece identity channel only. The original
discard-payment rule/heuristic, additional-cost checks, conditional mana
production/global state and other full-payer-context hooks are not turned into
a knowledge-aware public solver. Other valid-card/zone/ability-dependent costs
and global conditions remain unqualified. No independent family/random cohort,
full game, broader fairness/strength proof, app/save compatibility or new profile
qualification is claimed. Parent's disjoint stack-LKI changes are not composed
or tested in this candidate. Graph updates, commits and publication remain parent-
coordinated; this sidecar performs none.
