# Bounded Suspend Lifecycle

Integrated bounded engine, human UI and AI qualification. This is not whole-card
certification, exhaustive Suspend support or expert-play validation.

## Rules And Canonical Sources

Checked the [current comprehensive rules](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt)
(effective September 25, 2026), CR 116.2f and 702.62a-d, and the official
[Suspend release notes](https://magic.wizards.com/en/news/feature/murders-at-karlov-manor-release-notes).
The final-counter cast is optional under current rules, not the older mandatory
wording. Targets are announced at casting, never when suspending the card.

Unmodified Scryfall API records and their SHA256/IDs are pinned in
`backend/tests/fixtures/suspend_canonical/provenance.json`. Rift Bolt, Errant
Ephemeron, and Ancestral Vision exercise distinct spell types and costs; Aeon
Chronicler is a real variable-X Suspend negative control. Drannith Magistrate
and Ivory Mask are canonical prohibition/target-unavailability controls. No
user match, opponent hand, or saved private library is used.
Canonical Solemnity verifies that prohibitions on permanent counters do not
incorrectly stop counters being placed on an exiled Suspend card.

## Contract

- One complete printed `Suspend N-{mana symbols}` line on a normal single-face
  card, positive fixed N; generic and ordinary color/colorless/snow symbols
  are delegated to existing payment code. Snow payment is not newly certified.
- Hand `suspend` is a priority special action, paid at its printed cost, with no
  targets, stack object, cast event, spell count, or spell-cost modifiers.
  Existing casting timing/prohibitions still determine whether it can begin.
- Owner upkeep creates a respondable trigger while suspended; resolution
  removes one time counter. Last removal creates a separate optional-cast
  trigger. Countering those two triggers has different consequences.
- `suspend_cast` pauses resolution with an explicit decline choice and legal
  ordinary `cast_spell` announcements from exile. No automatic invented target
  or alternative-cost choice is supplied. Mana waiver does not waive taxes or
  supported additional costs; ordinary validation/admission remains in force.
- Permission belongs to the owner and exact exiled incarnation. Departure and
  re-exile cannot reuse a stale trigger. Declining leaves the counterless card
  exiled without a later free-cast permission.
- Creature spells receive timestamped haste through stack-to-battlefield entry,
  permanently lost at the first control loss or other departure. Snapshot
  serialization preserves this duration and paused cast continuations.
- Supported Suspend keyword lines are excluded from spell resolution text,
  not removed from canonical card data. Complete targeted-draw clauses use the
  ordinary draw handler. Complete non-hand-cast prohibitions are shared by
  normal casting and effect-casting, not matched by card name.

## Focused Checks

Use an isolated tracked-source checkout with no copied SQLite/cache/runtime
data. Existing API fixture tests create a local source-bound SQLite database;
the new API gate refuses main or NFS roots. External Python dependencies are
allowed; never point the source or SQLite path at the parent checkout.

```sh
MTG_ISOLATED_TEST_ROOT="$PWD" PYTHONDONTWRITEBYTECODE=1 \
  /home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q \
  backend/tests/test_suspend_lifecycle.py backend/tests/test_suspend_api.py
```

Both seats cover special action/payment/priority, no printed mana cost, owner
upkeep, separate final trigger, cast/decline, missing and disappearing targets,
mana taxes, exile-cast prohibitions, stale objects, countered abilities, haste
and control loss/departure, deterministic root-immutable actions, strict typed
HTTP requests, and restoration through the production persisted-match loader.
The HTTP gate uses the actual App API handlers with TestClient. It is not a
real browser or operating-system process-restart claim. Manual step/counter/
zone transitions are explicit controlled fixtures, not natural histories.

## Integrated Acceptance And Remaining Coverage

The parent composed engine, typed human controls and actual AI hooks qualify
together against `e4d8aa8`: 892 backend regressions, ten actual-App browser cases,
ten real-HTTP AI cases and frontend lint/build/unit/wire checks pass. Both seats
cover suspend, cast/decline, targeting, reload and representative real backend
restart. AI dispatch no longer treats the decline option as a card ID. Idle
investment remains conservative and does not displace known plays or answers.
See [human controls](suspend-human-actions.md) and [AI policy](suspend-ai-consumer.md).
Evidence is archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/suspend-e4d8aa8/`,
with separate private browser and HTTP archives. The subsequent `8f1fcc3`
metadata-import changes do not alter any gameplay, AI or frontend module in this
qualification. Existing broad corpus gap diagnostics remain conservative.

Variable-X/nonmana/hybrid Suspend costs, granted Suspend, multiple printed
Suspend abilities, non-normal faces, land-play variants, unusual counter
replacement effects, and additional card-specific Suspend triggers/effects
are not certified. Other time-counter-removal effects must use
`suspend.remove_time_counters` to emit the shared final-removal event; this patch
does not claim coverage of every such canonical spell. No historical repair.
