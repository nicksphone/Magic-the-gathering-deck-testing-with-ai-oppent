# Native Type-Note Controls

The `note_creature_type` mechanic now uses the existing explicit `choice_id`
button route. Both public TypeScript mechanic unions recognize it. Rendering
does not select or submit a type; the player clicks an offered option. Unknown
mechanic kinds still display the unsupported-control warning.

## Evidence

The configured mechanics test includes `note-creature-type-controls.mjs`.
It obtains actual Long List of the Ents legal views from the qualified native
backend fixture for both seats, validates the public wire contracts and renders
the actual Controls component with React SSR. Invoking the rendered Elf button
submits exactly `choose_mechanic` with `choice_id: creature-type:elf` and the
offered actor. Backend choice execution, legal-query purity, opposing-seat
privacy, no inferred choice and unchanged actor-view bytes are checked.

The focused test, complete configured `npm test` chain, `tsc --noEmit` and lint
all exited zero. Actual Vite production build completed in 1.30 seconds with
50 modules. Build cache and output were local evidence scratch, not shared
dependencies. The build used Vite's API with the existing React plugin rather
than claiming execution of the raw `npm run build` command. Python fixtures
ran with native SQLite and socket denial installed before application imports.
No database, HTTP server or exclusive SQL slot was used.

The first new fixture omitted zero-valued mana keys and failed wire validation.
Its log is retained; only the new fixture was corrected. The corrected fixture
then reproduced the original UI's unsupported-control failure before the UI
change. Both failure ledgers remain distinct from the successful results.

## Limits

This is a public-contract/rendered-callback certificate, not a manual browser
click, natural opening-hand trajectory, completed game, BO3 or AI-strength
certificate. Starting fixture positions are explicit. Backend rules, action
validation and source-reference semantics were not changed. Full release and
native copied-bind/APNAP acceptance remain open; live services were untouched.

Verified evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/type-note-controls-current-20261007/`.
