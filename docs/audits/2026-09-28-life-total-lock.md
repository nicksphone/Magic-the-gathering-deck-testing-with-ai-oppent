# Life-total-lock boundary (2026-09-28)

Status: bounded application-code repair with focused real-card fixtures. General life replacement and simultaneous combat-event certification remain open.

Verification: 1,104 backend tests passed in an isolated source/database copy. Frontend lint/build/unit checks passed; one seeded Burn/Dimir game replayed with the same log hash and no timeout. No browser fixture specific to the life lock or broad matchup sample was run.

## Rules evidence

[Wizards' Platinum Emperion ruling](https://magic.wizards.com/en/news/feature/ultimate-masters-release-notes-2018-11-29) confirms that damage is still dealt while its controller's life total cannot change, and that nonzero life payments cannot be made. The card's printed text is "Your life total can't change." The [Magic 2015 release notes](https://magic.wizards.com/en/news/feature/magic-2015-core-set-release-notes-2014-07-07) give Cruel Sadist's pay-1-life activated ability. These are real-card fixtures, not custom balance cards.

## Shared path

- `rules_engine/replacement.py` recognizes supported controller, opponent and all-player "life total can't change" text. Gain/loss checks and `can_pay_life` use it; paying zero remains allowed and paying exactly current life is allowed without a lock.
- `effects/handlers.py` consults the gain/loss checks. `rules_engine/damage_results.py` suppresses the life decrease but retains damage consequences, including poison from infect. Combat routes each lifelink gain through that same effect handler, so a locked controller gains no life while an unlocked opponent still can gain life from damage dealt to the locked player.
- `rules_engine/costs.py` and `rules_engine/entry.py` share payment availability instead of checking life totals separately.
- Six focused tests exercise the real Platinum Emperion wording, Sacred Foundry's entry payment, Vampire Nighthawk combat damage/lifelink, Glistener Elf's poison damage, Cruel Sadist's activated payment at exactly one life, and a generic additional-cost option. The additional-cost option tests the engine boundary; it is not presented as printed Lightning Bolt text.

## Still open

- Combat lifelink no longer uses direct life increments: [the follow-up lifelink audit](2026-09-28-lifelink-events.md) covers supported gain doublers, gain-to-draw conversion, human replacement choices and staged gain triggers. This does not certify general simultaneous replacement ordering or unsupported life-change wording.
- Life-payment triggers and costs outside the audited activated/additional/entry paths need an inventory and golden tests. No arbitrary-card Oracle guarantee follows from four fixtures.
- Other text families that constrain life totals or set them to a specific value need separate coverage; this audit only supports the listed "can't change" clauses.
