# Controlled Native Fog Boundary Audit

## Finding

**Confirmed private-library decision dependency in one native heuristic family.**
`ComputerUtil.hasAFogEffect(defender, ai, true)` imports the defender's externally
activatable cards without an attacker-visibility/public-knowledge gate. With
Experimental Frenzy, that list includes a library top visible only to its owner.
The ordinary native Default controller changes its actual attack defender when
the two concealed library cards are permuted, despite equal actor snapshots.

This is not a complaint about open decklists, known deck composition, hand counts,
or remembering a genuinely revealed hand. Both concealed variants contain the
same cards. No reveal callback or attacker viewing grant occurs in the failing
pair. A separate explicit-reveal positive control deliberately permits a changed
decision and is not counted as cheating.

## Exact Source Trace

All following paths are relative to local pinned Forge
`61e9442c433711a82258daca3236f936a1d6f70e`:

| Source Location | Boundary Or Gate |
| --- | --- |
| `forge-ai/src/main/java/forge/ai/PlayerControllerAi.java:933` | Actual `declareAttackers` callback delegates to the native brain. |
| `forge-ai/src/main/java/forge/ai/AiController.java:1524` | Ordinary native attack controller; simulation and flat Monte Carlo disabled in this fixture. |
| `forge-ai/src/main/java/forge/ai/AiAttackController.java:600` | `doAssault` calls `hasAFogEffect(defendingOpponent, ai, true)`; a detected Fog vetoes assault. |
| `forge-ai/src/main/java/forge/ai/AiAttackController.java:770` | `chooseDefender`: lethal assault prefers the opposing player, otherwise a planeswalker is preferred. |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java:1579` | Adds defender's external activation list before any `checkingOther` gate. This is the suspect read. |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java:1581` | Raw hand is included only when not checking another player. |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java:1585` | `REVEALED_CARDS` can legitimately supply remembered opposing hand cards. |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java:1598` | Card-zone owner/may-play gate is relative to defender, not attacker's knowledge. |
| `forge-ai/src/main/java/forge/ai/ComputerUtil.java:1602` | Requires native Fog API, skips certain human convoke/improvise paths, then checks defender can pay. No observer gate. |
| `forge-ai/src/main/java/forge/ai/ComputerUtilCost.java:544` | Cost feasibility is not permission for the attacker to know a card. |
| `forge-game/src/main/java/forge/game/player/Player.java:1396` | External list includes the defender's library through `getCardsPlayerCanActivate(this)`. |
| `forge-game/src/main/java/forge/game/zone/PlayerZone.java:46` | Owner predicate accepts owner look/play permission; no attacker is passed. |
| `forge-game/src/main/java/forge/game/zone/PlayerZone.java:109` | Library enumeration is limited to its actual first card. |
| `forge-game/src/main/java/forge/game/staticability/StaticAbilityContinuous.java:489` | Resolves native `MayLookAt$ You`; applies viewing grant at line 966. |
| `forge-game/src/main/java/forge/game/card/CardView.java:680` | Actual observer visibility gate. The fixture asserts the attacker cannot see either concealed card. |
| `forge-ai/src/main/java/forge/ai/PlayerControllerAi.java:579` | Legitimate native reveal callback populates remembered-card knowledge. |
| `forge-gui/res/cardsfolder/e/experimental_frenzy.txt:4` | Full card program grants owner-only top-card look and play permissions, not public reveal. |

The other `hasAFogEffect` caller at
`forge-ai/src/main/java/forge/ai/AiBlockController.java:1152` concerns blocker
evaluation with its `checkingOther` argument. Its broader behavior is not
qualified here. No second decision family was investigated dynamically.

## Controlled Position

The actor has one nonsummoning-sick native Craw Wurm and 20 life. Its opponent
has two life, a Forest, and Jace Beleren with its printed three loyalty counters.
The failing pair also has Experimental Frenzy. There are no blockers. The two
opposing library cards are Fog and Forest, created in identical identity order,
then permuted. All public counts, cards, owners, loyalty, phase and life agree.

The harness calls the real native controller, asserts that Craw Wurm actually
attacks, and compares its actual native defender. It does not install an attack
override, choose an attack for the AI, resolve combat, force a winner, concede,
or run a game/match cohort. The native position remains nonterminal.

The complete five original native card programs are in `canonical/`, compared
byte-for-byte before execution. See [attribution and provenance](NOTICE.md).
Jace's counters are a labelled constructed-board pose, not a fabricated rules
implementation. The native state-based-action check must retain it and native
combat must offer it as an attackable planeswalker.

## Runtime And Results

The qualified input is
`U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json`,
where `U=/home/nick/.hermes/cache/scratch/mtg-jev-ui-clarity-20261025-krVbf5Hv`.
Its build ID is
`59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605`.
The launcher reads its exact ordered 102-entry classpath and Temurin JDK
`21.0.13+9`, prepending only the new sidecar classes. It uses `--release 17`,
`-implicit:none`, an isolated sourcepath, 1,500 MiB heap, fresh local home/tmp,
sanitized environment, read-only external filesystem, isolated PID/network
namespaces, and a 180-second wall limit. No installation or native recompilation.

Profile is explicitly `Default`; simulation, all flat Monte Carlo modes,
filtered hands, and shuffle cheating are off. RNG is reset to `2026110601`
immediately before each actual callback. Ending RNG is recorded, not exposed as
a public fixture. The suspect helper is inspected only after the real decision
so its diagnostic call cannot prime a native spell or cost evaluator.

The final syscall-traced run observed **2 RED / 6 PASS / 0 errors**, exit 1.
The fixture-corrected diagnostic run independently observed the same counts:

| Matched Pair, Each Seat | Actual Decision | Result |
| --- | --- | --- |
| Concealed Fog/Forest top, Experimental Frenzy | Fog top: Jace; Forest top: opponent. Actor snapshots equal; ending RNG differs. | 2 RED |
| Same concealed permutation, no external-zone grant | Both attack opponent; snapshots and ending RNG equal. | 2 PASS |
| Concealed opposing hand identity, compensating library swap | Both attack opponent; snapshots and ending RNG equal. | 2 PASS |
| Explicitly revealed opposing hand identity | Known Fog: Jace; known Forest: opponent. Native remembered Fog changes legitimately. | 2 PASS |

Each cohort is eight paired checks / sixteen controlled decisions, not eight
games. Repeated executions of these checks are not independent coverage and
must not be added into one headline count. A RED result returns process exit 1.

The first diagnostic version omitted Jace's loyalty pose. Native state actions
removed it, so both variants attacked the player; the hidden read still changed
RNG. That run had 4 RED / 4 PASS, including two failed positive-control assertions.
It is retained as a fixture error, not evidence of differing attack decisions.

The final execution pins twelve actual loaded class resources before and after;
all match, as do the JDK executables/release and compiled Java input. In particular,
native `ComputerUtil.class` is
`d20f288d1d3cc576c9aab9ecedf80a918d7aef2830b23a0df27b79d829aa6160`;
native `AiAttackController.class` is
`82a10f7ea88698b312663f00ec49ab54a9f5e32de453a21ab5d491a16f70fa78`.
Both load from the qualified Forge `forge-ai/target/classes`, not sidecar shadows.

Network isolation was enforced. The final syscall trace records zero IP connects
and zero non-netlink sends. It does record three IP-family socket creations,
two unsuccessful Unix-domain connects, and local netlink interface queries.
This is not a claim of zero attempted socket/IO activity. A preceding unfiltered
strace attempt reached its 180-second bound during native initialization before
any checks; its launcher also encountered a tail parse error after an in-flight
launcher edit. Neither failure is relabelled as a test result. The final frozen
launcher uses seccomp-BPF syscall filtering and completed normally with the two
intended regression failures.

Private evidence destination:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/native-fog-boundary-audit-20261106-fCgiXcqU/`.
The archive includes every diagnostic stage, final source/launcher and full card
programs, exact selected native source hashes/copies, loaded class origins/hashes,
JDK pins, full classpath/argv, final syscall log, and the confined AST graph refresh.

## Reproduce

With the already installed pinned native resources and dependencies:

```sh
bash tools/engine_evaluation/forge/ai-boundary/run.sh \
  "$U/native-causal-cold-resume-qualification-20261106-Vi32VEl0/BUILD-IDENTITY.json" \
  "$U"
```

The launcher requires existing `jq`, `bwrap`, `strace`, and the pinned JDK. It
prints the fresh local scratch path and aggregate counts only. Its stdout,
generated actor/native information, RNG and syscall logs are private evidence.
Archive to the verified mounted NFS share, byte-verify the archive, then clean
successful disposable local scratch. Do not commit generated evidence.

## Limits And Follow-Up

This is an actionable ordinary-native-AI fairness finding for one specific
private-top-card mechanism, not evidence of cheating in user games, a strategic
strength benchmark, or a whole-AI fairness proof. It does not qualify every
hand/library consumer, remembered-card lifecycle, multiplayer disclosure,
cost variant, card, combat scenario or live application configuration.
The earlier bounded draw/counter checks remain separate limited evidence.

A future production correction should use actor-authorized public/remembered
knowledge when assessing an opponent's external-zone options, without removing
legitimate owner-side knowledge or public remembered reveals. It needs separate
authorization, implementation and requalification; no production fix is made by
this sidecar. No broad randomized cohorts, SQL, app service, HTTP, live matches,
protected model bodies, secrets, or dependency installs were used.

Only new files in this directory are authored. No commit/push or shared graph
rewrite is performed. The AST graph refresh runs only on a copied sidecar source
in owned local scratch; the shared graph was already stale at inspection.
