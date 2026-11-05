# External Engine Card Knowledge

Evaluated 2026-11-05. The live app remains on its existing Python engine.

| Check | Forge | XMage |
| --- | --- | --- |
| Shipped canonical card definitions | 155/155 | 155/155 |
| Additional hard-card reference list | 32/32 | 32/32 |
| Original four-card, both-seat native compatibility tests | 8 passed | 8 passed |
| Selected unmodified upstream native tests | 125 passed | 8 passed |
| Additional headless human-controller callback check | 1 passed | Not exercised |

Each successful native cohort had zero failures, errors or skips. The upstream
cohorts differ: their counts do not rank one engine's quality above the other.
The shared-card tests cover actual native effects/payment, not just matching
card names. Full inputs and assertions are in the
[credited evaluation adapters](../../tools/engine_evaluation/README.md).

Forge's upstream cohort covers its game-simulation and replacement tests.
XMage's selected methods cover draw-trigger, graveyard shuffle/foreign control,
zone-change replacements, Humility, blink and landfall behavior. These are
bounded engine checks, not universal correctness or expert-play certificates.

The 32-card source reference includes haste/prowess, draw, cast and ETB triggers,
replacement shuffles, ability loss, cycling, targeted land search, temporary
control, immediate blink, dredge and sacrifice mana. Full canonical references
were obtained from the hash-verified official Scryfall Oracle bulk snapshot.
The shipped reference is the unchanged `builtin_oracle_seed.json`.

## Important Distinction

Both projects have executable card knowledge, not merely Oracle text. Forge
uses card programs and XMage uses Java card/effect implementations. Copying
names or descriptions into our current engine would not reproduce that behavior;
the meaningful shortcut is an engine integration, with its rules and controllers.

## Recommendation

Start the next isolated integration prototype with **Forge**. Both candidates
cover our reference lists and common-card cases; Forge additionally demonstrated
an in-process human-controller callback/state-delta path without a network
server. That is useful evidence for preserving our own UI. The check played a
human land and received state/decision events; it was not a full human/AI game.

XMage remains a credible alternative, including its server architecture and
MIT terms. This recommendation does not declare Forge's AI stronger, approve
production migration or bypass Forge's distribution/license review.

The next integration gate must exercise real user decisions and hidden-information
boundaries through our API, a complex completed match, sideboarding, restart/save
behavior and packaged startup. The current app and saved data remain untouched
until those checks justify a cutover. No Rust rewrite or new custom training fit
was needed for this evaluation.

## Retained Setup History

The first source-name lookup missed XMage's five basic lands because they are
in its core module; the corrected lookup found all five. This was not missing
card support. Forge's first two build launches were harness/JDK setup failures.
XMage retained three zero-test offline dependency failures. Its first original
compatibility cohort had two Growth Spiral harness-choice errors; the sole
correction changed `addTarget(actor, "Plains")` to `setChoice(actor, "Plains")`.
Every outcome assertion was retained. Those histories were not relabelled green.

Source archives, full Maven logs, native JUnit XML, fixture revisions and byte
verification receipts are retained in protected project storage. No private
synthetic game trace or model weights were published with this report.

See [third-party authorship and licensing](../../THIRD-PARTY-NOTICES.md).
