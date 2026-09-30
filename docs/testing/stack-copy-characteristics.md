# Surviving Spell Copy Characteristics

A spell copy keeps the chosen characteristics of the copied spell. The physical card can subsequently move to another zone and regain its printed face without changing the copy. The copy rules are described in [Wizards' Comprehensive Rules, section 707](https://media.wizards.com/2024/downloads/MagicCompRules20240917.pdf).

Target generation, ordinary and taxed counter resolution, stack resolution and AI threat scoring now share `stack_source_card`. It reads the copy's snapshot-persistent `__copied_card` values, sets its current stack controller, and leaves the physical card unchanged. This replaces separate readers that could confuse a surviving Stomp copy with the departed Bonecrusher Giant creature, or a copied Fire with the combined Fire // Ice mana cost.

Canonical Negate, Spell Pierce, Spell Snare and Disdainful Stroke fixtures exercise noncreature, exact mana value and minimum mana value filters. The general Oracle target parser recognizes the supported `with mana value N` and `with mana value N or greater` forms; spell X values remain part of the restriction calculation. Conditional resolution clauses, such as Prohibit's `if its mana value is ...`, are a separate mechanism and are not certified by these tests.

The regressions cover:

- A copied Adventure instant remaining a legal noncreature-counter target after the original is countered and its physical card returns to the graveyard.
- Ordinary and taxed counter resolution removing only that copy.
- Spell Snare using the copied half's mana value of two rather than the combined off-stack card's four.
- Disdainful Stroke using copied Tibalt's mana value of seven rather than the restored physical card's two.
- Invalid mana-bound counter submissions rejected without state mutation.
- Snapshot restoration, unchanged physical-card characteristics, and Control AI scoring/countering a surviving planeswalker copy.
- Human Negate selection and resolution through the existing browser target control.

These checks cover spell-copy characteristics in the supported target and counter paths. They do not certify all counter conditions, copy layers, legacy snapshots without copied-characteristic metadata, or complete Fuse casting. Fuse remains on the active plan.
