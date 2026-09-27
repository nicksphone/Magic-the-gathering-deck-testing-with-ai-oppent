# Crew Stack Timing

[Wizards' Kaladesh release notes](https://magic.wizards.com/en/news/feature/kaladesh-release-notes-2016-09-16) define crew as an activated ability. Tapping eligible creatures pays the activation cost; other players can respond to the ability on the stack. The same notes say recently controlled creatures may crew, and a Vehicle already a creature may be crewed again.

The engine now taps the selected crew when activating, adds a `crew_vehicle` ability to the stack, and grants artifact/creature types only when it resolves. Countering the ability leaves the tap cost paid but does not animate the Vehicle. Removing a crew member after activation does not change the result. The ability follows the same battlefield Vehicle across a control change, but not a Vehicle that has left and returned as a new object. Cleanup removes only types this crew effect added.

`backend/tests/test_vehicles.py` uses canonical Smuggler's Copter and Soul Warden metadata. It checks paid costs, stack timing, snapshot recovery, countering, crew-member loss, control change, leave/re-entry, cleanup and repeat activation. The browser human-action harness exercises the production API/React response path with named real-card fixtures.

Validation on 2026-09-27: 861 isolated backend tests, frontend production build/unit checks and twelve Chromium action paths pass. A seeded two-game BO3 replay finishes in 40 turns without timeout or determinism drift. This is not a balance or AI-strength result.

Still open: "becomes crewed" triggers, Vehicle copies and complex layer interactions, and full-game competitive acceptance. The AI selects a legal crew group and filters redundant activations, but these tests do not measure whether crewing is strategically optimal.
