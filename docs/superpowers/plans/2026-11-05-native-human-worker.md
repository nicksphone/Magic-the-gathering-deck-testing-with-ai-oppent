# Native Human Worker

Use the existing isolated branch, pinned Forge source and cached classpath.
This continues the native-engine adoption evaluation, not a live cutover.

## Design

One native human-versus-AI game runs in an offline JVM, using Forge's unchanged
HostedMatch, ProtocolGuiGame and human controller. JSON lines cross stdin/stdout.
Redirect native diagnostics to protected stderr before initialization. Reuse
ActorBoundary for detached actor-visible snapshots and one-use choice tokens;
never transmit native GameView, deltas, controllers, raw events or game logs.
The process is bound to its host-selected actor; replies cannot select a seat.

Use native Selection/actionable cards, player targets and enabled buttons for
clicks. Route replies through the unchanged IGameController on the native EDT.
Blocking dialogs retain native values privately and receive explicit answers;
unsupported types/dialogs fail closed rather than silently choose a default.
Expire replaced tokens; reject malformed/oversized/unknown replies without
consuming valid choices. EOF aborts the worker, never manufactures a winner.

## Execution

1. Test strict reply parsing before implementing it. Add the worker without
   changing upstream source or the app. Preserve GPL headers and upstream credit.
2. Run actual out-of-process tests: valid native human land/spell/target/payment
   choices, stale/forged/malformed rejection and actor-visible privacy. Continue
   a natural human-controller-versus-native-AI game where supported. A scripted
   test client is not evidence of expert human or AI play.
3. Run the declared unchanged native regression neighbors, review the transport,
   publish precise results and archive closed evidence on mounted NFS. Keep
   original live matches/data and protected traces unchanged.

No raw-state persistence is assumed. Native save/RNG/choice continuation, all
dialogs, browser/API/auth integration and distribution review remain requirements
before adoption. Do not replace the whole goal with this transport checkpoint.
