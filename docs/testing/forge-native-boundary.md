# Forge Actor Boundary Prototype

Pinned engine: Forge `61e9442c433711a82258daca3236f936a1d6f70e`.
The Forge Team/Card-Forge contributors authored the native engine, controllers
and card programs. Our separately GPL-3.0-or-later prototype and tests credit
that work in their headers. See [the original license and notices](../../THIRD-PARTY-NOTICES.md).

## Actual Evidence

Five whole native test classes passed **154 tests**, with zero failures or skips,
in 14.205 seconds of TestNG suite time. They comprise our 26 actor-boundary cases,
our two in-process human-controller cases, and unchanged upstream game simulation
(124), replacement (1) and in-process controller (1) cases. This is not the whole
Forge test suite or an application release gate.

The boundary cases run both seats on native constructed positions. They check
own-hand visibility, concealed opposing hands/libraries, hidden-order byte
invariance, actual viewing grants and revocation, face-down battlefield/exile,
foreign-game rejection and scalar-only payloads. Choice tests cover opaque tokens,
wrong actors, forged/duplicate/stale/null answers, optional declines, order,
unsupported values, prompt invalidation and unclassified card rejection.

The later [retained stack-source correction](native-deck-quality-2026-11-06.md)
adds an exact-native-entry, public face-up battlefield-LKI path for stack
projection only. It does not relax ordinary unclassified card rejection.

Two actual native human-controller cases passed token answers through Forge's
`ProtocolGuiGame`/`IGameController`. A land really entered the battlefield; wrong
actors and forged answers were rejected before native action. Each game then
ended by harness concession. These are not complete human/AI games, browser
tests or strategic-play certificates.

## Why A Projection Is Required

Raw native views, tracked deltas and events contain private objects and card
identities. The prototype rebuilds primitive JSON-shaped data for one actual
registered actor instead. It copies fields during the trusted callback, before
temporary permissions can expire. It checks both card and face-down visibility;
native image keys, alternate object graphs and arbitrary raw messages are not
forwarded. Pending native choice values remain server-side.

Review caught an additional leak: the native `Flashback` collection is a virtual
availability list, not a physical-zone count. An opponent-only library viewing
grant changed that raw count, despite concealing the card's name. The corrected
projection includes only the supported physical zones, not virtual lists or
variant decks with different disclosure rules.

The host must resolve the authenticated caller itself, never accept a client's
chosen actor ID. It must invalidate requests on timeout, disconnect, prompt
replacement and game end. The test receiver wires native input replacement,
timeout and game-end invalidation. Invalid answers do not consume the genuine
question; successful answers consume it once.

## Remaining Work

The `Remote` in the test is a limited driver, not a production protocol adapter.
It exercises encountered land/ability and basic dialog paths, not all native
choice types. Production authentication, complete native dialog support, actual
reveal callbacks, browser integration, saved pending games and packaged startup
remain unfinished. A private viewing-grant fixture is not proof that every real
card's reveal lifecycle is integrated. Explicit physical-zone output does not
qualify unsupported game variants.

No live backend, UI or saved match was changed. The adoption decision is to
continue the isolated Forge integration work, not switch the application yet.
AI strength and private-information use by the native AI need their own reviews.

### Native AI Fairness Caution

A separate source review found that the shuffle-cheat flag blocks mana weaving,
not every private-information read. At the pinned revision,
`PlayerControllerAi.chooseCardName` and `NamedDiscard.chooseName` include paths
that inspect the opponent's actual remaining library. Disabling Monte Carlo
does not remove those heuristic paths. `FILTERED_HANDS` is another, separate
setting, defaulting false; future comparisons should explicitly set and record it.

These source paths were not shown to execute in the BO3. Its completion remains
lifecycle evidence, not proof of fully imperfect-information play. Native AI
adoption requires further tests and comparison, not just the safe client view.

## Retained History

The initial closed stub failed all 16 tests, then the implementation passed them.
Two added null-token cases first failed with `NullPointerException`; validation
was fixed without consuming the request. The earlier five-class 148-pass run
predates review's virtual-count and lifetime findings. Six added tests reproduced
those findings before the final 154-pass correction. All raw stages and generated
game logs remain in protected evidence storage, not public Git fixtures.

See [the credited code and invocation](../../tools/engine_evaluation/README.md#actor-boundary-prototype)
and [the independent BO3 evidence](external-engine-card-knowledge.md#first-complex-native-match).
