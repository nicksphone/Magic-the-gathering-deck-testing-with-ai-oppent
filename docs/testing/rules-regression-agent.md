# Rules regression agent — independent handoff

## Result and scope

Base: `f35cb4bc8fc21f6f166e2eb4ec621fc875ce08ad` (committed main). Branch: `tests/rules-regression`. Worktree: `/home/nick/mtg-rules-regression`.

**30 new deterministic cases: 16 passing, 14 failing, zero skipped/xfail.** Five confirmed behavior gaps; Remand has two independently asserted broken outcomes. Both seats are exercised. No engine fixes, existing-test edits, dependency changes, shared Graphify changes, merge, or push.

These are **interaction positions**, not legal tournament decks: canonical Island filler, explicit public positions, abundant mana, seed `20261004`. They cover burn/green creature **aggro** resources and blue/white/black **control/recursion** responses. They do not measure AI policy, matchup balance, win rates, or certify whole-card support. Printed Oracle text is never altered. Initial battlefield permanents represent already-established positions (their ETBs are not replayed).

## Ranked confirmed findings

All node IDs below are under `tests/regression_agent/test_interactions.py::`. Exact expanded failing IDs are listed later. Numeric expectations are assertions from canonical effects, not fitted to engine output.

### 1. Remand drops both its draw and conditional hand destination

- `test_remand_response_preserves_conditional_destination_and_draw[draw-counterable-{1,2}]` and `[draw-uncounterable-{1,2}]`: expected response player's hand count **8** (Remand spent, one card drawn); actual **7**. Four failures.
- Same test `[destination-counterable-{1,2}]`: expected countered Grizzly Bears in owner's **hand**; actual **graveyard**. Two failures.
- `[destination-uncounterable-{1,2}]` passes: Allosaurus Shepherd stays on stack, then resolves to battlefield. This does **not** excuse the missing draw.
- Actual checked creature cast → active player passes → opponent pays two mana and casts Remand → snapshot restore → two checked priority passes. Remand itself reaches graveyard. Draw/destination are separated so one failure cannot conceal the other.
- [Remand canonical record](https://api.scryfall.com/cards/a5048047-abff-4a1f-8d72-6b758a03542c), Oracle ID `d71cd08e-3e84-41ff-b9db-9e343c0af6b4`. Ruling **2021-03-19**: “Remand can target a spell that can't be countered. That spell won't be countered or returned to its owner's hand, but you'll draw a card.” CR **608.2c, 609.3, 701.6**.
- Classification: **compound-effect parsing/resolution defect**, not a priority or payment fixture error. Diagnostic inference returns only `counter_spell`. `known_unsupported_mechanics` misleadingly reports `player-counter replacement fidelity` here; it is not a specific Remand implementation guarantee.
- **Proposed repair locations, not changes:** `rules_engine/oracle_effects.py:306–329` early counter return; `effects/handlers.py::counter_spell` and stack departure rules for conditional destination. Preserve unconditional subsequent instructions even when countering is impossible; retain flashback exile replacement precedence.

### 2. Reanimate returns the creature but omits its life loss

- `test_reanimate_enemy_graveyard_preserves_owner_and_loses_life[{1,2}]`: expected caster life **18** after returning mana-value-two Grizzly Bears; actual **20**. Owner remains opponent and controller correctly becomes caster; returned zone assertions pass before the failure.
- [Reanimate canonical record](https://api.scryfall.com/cards/368b6903-5fc4-43e7-bd44-46b8107c8bb4), Oracle ID `a044474a-cd72-4e9d-bd8d-a08f2de9cdc0`. Oracle ends “You lose life equal to that card's mana value.” Rulings **2025-09-19** explicitly place life loss after battlefield entry, before ETB triggers resolve; mana value is determined from the graveyard card. CR **608.2c**.
- Classification: **partial spell implementation**. Inference emits only `return_creature_from_graveyard_to_battlefield`; coverage diagnostic returns `[]`, which is not certification.
- **Proposed:** `rules_engine/oracle_effects.py:1660–1665`, return handler and resumable effect sequences in `effects/handlers.py`. Preserve the referenced graveyard object's mana value and apply subsequent life loss after entry, including entry-choice pauses. Those pause cases are not tested here.

### 3. Furnace of Rath's canonical damage replacement is ignored

- `test_two_furnaces_replace_bolt_each_once[{1,2}]`: one Furnace under each controller, actual paid Lightning Bolt at opponent. Expected **12 damage / life 8**; actual **3 damage / life 17**.
- [Furnace canonical record](https://api.scryfall.com/cards/d7f0e720-3c32-4040-b663-7f99ad5bc810), Oracle ID `68715465-6cf9-4006-87e9-31f227fe9ed3`. Ruling **2004-10-04**: “If you have two of these on the battlefield, the damage is multiplied by 4.” CR **614.5, 616.1**. Its **2005-08-01** ruling explains affected-player ordering against prevention.
- Classification: **unsupported replacement family / missing implementation**, not proof of a subtle ordering bug. Because neither doubler works, this test cannot certify affected-player choice ordering against unlike replacements. It does exercise competing canonical sources and controller independence.
- **Proposed:** `rules_engine/replacement.py::replacement_options`, player/permanent candidate collection and damage replacement chain. Existing player candidates at lines 136–140 recognize narrow controller-scoped prevention, not this global doubling clause. Do not implement it as prevention (Skullcrack must not disable doubling).

### 4. Young Wolf's undying never returns it

- `test_stolen_undying_returns_only_after_actual_death[dies-{1,2}]`: stolen Wolf has no +1/+1 counters; Doom Blade resolves. Expected return to battlefield under **owner's** control with one +1/+1 counter; actual stays in **graveyard**, no returning trigger settles.
- `[exile-replacement-{1,2}]` passes: Rest in Peace instead exiles the Wolf to its owner's exile and it never returns. That branch alone is not proof undying is implemented.
- [Young Wolf canonical record](https://api.scryfall.com/cards/ed2ca825-b029-495f-83fc-54366229d417), Oracle ID `8b492764-10b6-4506-be11-22daa9220a91`. Scryfall ruling list is empty; authority is Oracle keyword plus CR **702.93a** (exact excerpt pinned). Undying is a triggered ability, not an immediate replacement.
- Classification: **unsupported keyword / missing death trigger**, not a known working undying feature regression. Source search found no undying implementation; diagnostic unsupported list also returns `[]`.
- **Proposed:** `rules_engine/events.py` death/LKI collection, stack triggers, and entry-counter/zone-incarnation machinery. Follow original owner, examine counters before departure, and ensure an old trigger cannot return a new graveyard incarnation. The latter is an untested repair acceptance requirement, not a reproduced failure here.

### 5. Cremate cannot legally be announced at an existing graveyard card

- `test_reanimate_removed_target_does_not_return_or_lose_life[{1,2}]`: opponent has priority, sufficient mana and a real graveyard card while Reanimate is pending. Expected Cremate announcement succeeds, exiles the target, then Reanimate fails to resolve without life loss. Actual **ActionRejected: Action is not currently legal** at Cremate announcement.
- [Cremate canonical record](https://api.scryfall.com/cards/013d5260-f906-4f6a-97ed-725197743b60), Oracle ID `c6a2e410-b182-48d1-aeb2-bc8de27e9cd2`. Ruling **2012-10-01** requires a target card in a graveyard (present here). Oracle: “Exile target card from a graveyard. Draw a card.” CR **117.3c, 117.4, 608.2b**.
- Classification: **target-admission integration gap**. Diagnostic target hints are `{}`, despite inference recognizing exile plus draw. The planned Reanimate illegal-target continuation is **blocked and unverified**, not claimed defective.
- **Proposed:** `rules_engine/oracle_effects.py::inspect_target_hints` (graveyard target branch lines 886–921 only handles return/put/reanimate wording), cast target admission and zone-aware exile handling. The generic exile handler's graveyard behavior must also be reviewed; announcement repair alone is not sufficient evidence.

## Passing coverage and remaining uncertainty

- Replacement/prevention: current Skullcrack text disables prevention **before its own damage**; pre-existing three-point shield remains unconsumed per CR 615.12, two mana paid, snapshot and final spell zone checked. Shield is an explicit rules-level fixture field, not a claim about Healing Salve parsing. Older existing Skullcrack test uses reordered text and does not assert this particular ordering.
- Continuous effects: Humility base 1/1 → +1/+1 counter + anthem + Giant Growth = 6/6; Disenchant removes anthem → 5/5; printed stats remain 2/2. Snapshot-restored explicitly declared unblocked combat deals five. Attack/block declaration selection is not under test in this position.
- Zones: paid Giant Growth → Unsummon → snapshot → paid recast resets counters and temporary pump; creature is 2/2 and summoning sick. This complements existing low-level zone-reset tests with full spell announcements.
- Graveyard permission: Think Twice flashback pays three, opposing Counterspell resolves after snapshot, Think Twice is exiled with no draw and no refund. Ordinary graveyard Lightning Bolt is rejected without any snapshot mutation.
- Priority: Remand before opponent receives priority is rejected atomically. The actual permitted response is tested independently.
- Stack copies: **existing** `test_stack_copies.py` and `test_copy_stack_characteristics.py` ran in the combined selection, not newly implemented here. Unlike replacement ordering, discard-trigger chains, more layer dependencies, ETB life-loss continuations, delayed undying incarnation validity, and full matchup/AI behavior remain unverified.
- No line/branch coverage percentage: `pytest-cov` is not installed; dependencies were not modified. Scope is measured by executed cases and assertions, not an invented percentage.

## Verification and reproduction

Tests ran **only** in a disposable `git archive HEAD` tracked-source copy, never the live checkout or worktree. Source-relative SQLite/cache paths therefore resolve under the disposable source. No credentials, servers, or live DB/cache were used. Original dirty AI files and concurrent UI worktree were untouched.

Retained local root (do not clean until parent independently reruns):
`/home/nick/.hermes/cache/scratch/rules-regression-20261004T203843Z`

Interpreter (existing dependencies, not a copied live source):
`/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`

```sh
cd /home/nick/.hermes/cache/scratch/rules-regression-20261004T203843Z/source/backend
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q -ra tests/regression_agent
```

Expect exit **1**, **14 failed / 16 passed** on the recorded base. `run.py` in the retained root records full commands, environment overrides, logs and JUnit XML; it prints the pytest exit code but the wrapper itself exits normally. Use the command above for the real pytest shell exit status.

| Run | Scope | Result |
|---|---|---|
| baseline | Six existing files, before new tests | 108 passed; 66 deprecation warnings |
| investigation | Initial 18 cases | 8 passed, 10 failed |
| expanded | 28 cases, split Remand assertions and added permission/target cases | 14 passed, 14 failed |
| final-new | Final 30 cases | 16 passed, 14 failed |
| repeat-new | Same final 30 cases | 16 passed, 14 failed; identical node outcomes/messages |
| combined | Final new cases plus ten relevant existing files | 181 passed, 14 failed; 4 deprecation warnings |

Combined selection (full command and absolute XML/log destinations in `evidence/commands.jsonl`):

```sh
python -m pytest -q -ra tests/regression_agent \
 tests/test_prevention_replacement_edges.py tests/test_damage_replacements.py \
 tests/test_temporary_ability_loss.py tests/test_zone_object_reset.py \
 tests/test_counterability_scope.py tests/test_priority_stack.py \
 tests/test_stack_copies.py tests/test_copy_stack_characteristics.py \
 tests/test_death_replacement_canonical.py tests/test_combat_damage_windows.py
```

The first six existing files constitute baseline. All **165 existing cases** in the combined run pass. **No full-suite claim.** Programmatic JUnit reconciliation confirms the final new-case outcomes are identical alone, repeated, and combined. AST parsing and `git diff --check` also passed. One exploratory diagnostic import used the wrong helper name (`build_cast_hints` in `oracle_effects`); corrected to actual `inspect_target_hints` before producing parser diagnostics. No production code changed.

## Provenance and evidence

`backend/tests/fixtures/regression_agent/cards.json` pins **19** full Scryfall card records plus fetched ruling responses, exact request URLs, printing and Oracle IDs, and UTC retrieval timestamps on **2026-10-04**. No test performs network I/O. Empty ruling lists are retained as empty, not invented. `rules.json` pins relevant exact excerpts and URL from the Wizards rules landing page's current **2026-09-25** Comprehensive Rules:

- <https://magic.wizards.com/en/rules>
- <https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt>

The graph report was read fully first. Wiki index and nested AGENTS.md are absent. Ancestor `/home/nick/AGENTS.md` applies. Graph built at `a69233fa` is stale against base; source inspection confirmed proposed locations. Read-only graph query output is retained. Per assignment, graph update is reserved for the backend agent.

Archive directory:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-agent/20261004T203843Z`

Evidence includes full pytest logs/XML, machine-readable counts and node outcomes (`results.json`), parser diagnostic outputs (not substitutes for gameplay tests), complete downloaded rules, setup/reproduction scripts, owned-file copies, base source archive, committed source bundle, and SHA-256 manifest. NFS mount and write/read/delete probe were checked; archived file hashes are checked against local originals. Local runtime is deliberately retained for independent review.

## Exact failing node IDs

```text
tests/regression_agent/test_interactions.py::test_two_furnaces_replace_bolt_each_once[1]
tests/regression_agent/test_interactions.py::test_two_furnaces_replace_bolt_each_once[2]
tests/regression_agent/test_interactions.py::test_stolen_undying_returns_only_after_actual_death[dies-1]
tests/regression_agent/test_interactions.py::test_stolen_undying_returns_only_after_actual_death[dies-2]
tests/regression_agent/test_interactions.py::test_reanimate_enemy_graveyard_preserves_owner_and_loses_life[1]
tests/regression_agent/test_interactions.py::test_reanimate_enemy_graveyard_preserves_owner_and_loses_life[2]
tests/regression_agent/test_interactions.py::test_remand_response_preserves_conditional_destination_and_draw[draw-counterable-1]
tests/regression_agent/test_interactions.py::test_remand_response_preserves_conditional_destination_and_draw[draw-counterable-2]
tests/regression_agent/test_interactions.py::test_remand_response_preserves_conditional_destination_and_draw[draw-uncounterable-1]
tests/regression_agent/test_interactions.py::test_remand_response_preserves_conditional_destination_and_draw[draw-uncounterable-2]
tests/regression_agent/test_interactions.py::test_remand_response_preserves_conditional_destination_and_draw[destination-counterable-1]
tests/regression_agent/test_interactions.py::test_remand_response_preserves_conditional_destination_and_draw[destination-counterable-2]
tests/regression_agent/test_interactions.py::test_reanimate_removed_target_does_not_return_or_lose_life[1]
tests/regression_agent/test_interactions.py::test_reanimate_removed_target_does_not_return_or_lose_life[2]
```

Backend owner: independently rerun, classify unsupported scope deliberately, repair shared paths, then expand regression coverage before integrating. Keep failures intact; no blanket xfail/skip.
