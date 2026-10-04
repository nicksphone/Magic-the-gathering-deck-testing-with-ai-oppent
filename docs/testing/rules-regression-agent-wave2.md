# Rules regression agent — wave two

## Outcome and scope

Bounded tests-only investigation: **40 new cases, 34 passing and 6 failing**.
The six failures represent five findings in four card families, detailed below.
No xfail, skip, production changes, existing-test edits, dependency changes,
services, first-wave edits, merge, reset, rebase, or push were used.
This is not arbitrary-card support or expert-AI certification.

- Starting branch: `tests/rules-regression`.
- Starting HEAD / tested production base: `701cd191bb28fdcd5fa56a5bc6099a4c634e2ddc`.
- Common ancestor with main: `f35cb4bc8fc21f6f166e2eb4ec621fc875ce08ad`.
- Independently extracted, tested committed main: `26c973449fa25591b6fc99d873512b13d8225e92`.
- Main differs in production only in `backend/ai/agent.py` and
  `backend/ai/information.py`; its additional resource-forecast tests and shared
  documentation/graph also differ. The branch includes first-wave files absent
  from that main commit. No uncommitted main content was read into either copy.
- The final handoff commit is recorded in archive `commit.json` and the agent's
  handoff; this report is itself part of that commit.

All four final executions (branch twice, committed main twice) produced
**370 passed, 6 failed, 17 warnings**, including **336 relevant existing tests**.
The complete recorded new-case traces were byte-identical across all four runs.
Game RNG seed and `PYTHONHASHSEED` were both **731**.

## Ranked findings — assertions remain FAIL

Test filenames below are under `backend/tests/regression_agent_wave2/`.
“Confirmed” means an observed mismatch against the cited rule, not a claim that
all surrounding card functionality was previously supported.

### 1. High: Fling consumes mana and the creature but resolves as a no-op

- `test_casting_contracts.py::test_fling_sacrifice_target_and_lki[p1-lki]`
- `test_casting_contracts.py::test_fling_sacrifice_target_and_lki[p2-lki]`
- Expected: sacrificing Grizzly Bears with two +1/+1 counters pays the cost,
  preserves its last battlefield power of four, and deals four damage to the
  opponent. Fling's ruling explicitly requires that last-known power.[41]
- Actual: checked announcement succeeds, `{1}{R}` and the creature are paid;
  stack effect is `noop`, log says Oracle effect was not inferred, and the
  opponent stays at **20**, not **16**, after snapshot restore and resolution.
- Classification: unimplemented cost-linked effect admitted by legal moves and
  checked casting; not a proven arithmetic/LKI-cache bug. Coverage diagnostics
  returned no known unsupported mechanics for the canonical text.
- Reproduces on committed main: **yes, twice**.
- Proposed shared repair, not implemented: connect
  `costs.apply_additional_costs` / sacrifice bookkeeping to a structured spell
  effect in `oracle_effects.py` and its stack payload; retain paid-creature LKI
  durably, or explicitly gate unsupported semantics before consuming resources.
- Passing boundary: targeting the creature sacrificed for the cost correctly
  causes non-resolution when that sole target has left the battlefield. This
  does not certify Fling's effect parser (that stack packet was `sacrifice`).

### 2. High: Incremental Growth accepts duplicate “different” targets

- `test_casting_contracts.py::test_incremental_growth_rejects_duplicate_target_before_payment`
- Expected: reject `[bear-A, bear-A, bear-B]` and preserve authoritative state;
  the ruling requires **three different targets**.[53]
- Actual: checked action returns an accepted paid candidate. The caller's
  original state remains unchanged because checked actions clone it; this is
  **illegal acceptance**, not a claim that the original object mutated.
- Reproduces on committed main: **yes, twice**.
- Proposed shared repair: preserve occurrence-specific/distinct-target
  constraints through `oracle_effects.build_cast_hints`, `targeting.py`, and
  `action_validation.py`; do not globally ban repeat targets, since separately
  occurring target clauses can sometimes target the same object.[24]

### 3. High: Incremental Growth drops the second and third effects

- `test_casting_contracts.py::test_incremental_growth_distinct_targets_keep_announced_counter_amounts`
- Expected: three distinct announced creatures receive **1, 2, 3** counters,
  with the announced allocation preserved across restart.[53]
- Actual: payment succeeds, stack contains one `add_counters` packet with
  `amount=1`, and final counters are **[1, 0, 0]**.
- Reproduces on committed main: **yes, twice**.
- Proposed shared repair: compile an ordered multi-target instruction sequence,
  persist per-occurrence target assignments, then independently revalidate each
  target at resolution. This is distinct from the announcement defect above.

### 4. Medium: Snapcaster Mage's grant is admitted as a no-op

- `test_casting_contracts.py::test_snapcaster_flashback_can_add_kicker_after_restart`
- Expected: the targeted Burst Lightning gains flashback; paying its flashback
  cost plus kicker is a legal combination. Snapcaster's ruling explicitly
  permits additional kicker costs while disallowing another alternative cost.[87]
- Actual: the only eligible graveyard instant is present; Snapcaster is paid and
  enters; its ETB stack item is `noop`. After it resolves, **no Burst Lightning
  legal move exists**. The assertion stops there.
- Classification: **missing granted-flashback implementation**, not a confirmed
  bug in the subsequent flashback+kicker payment branch. That combination is
  still unverified end-to-end. Native Firebolt and Devil's Play flashback and
  ordinary Burst Lightning kicker pass separately.
- Reproduces on committed main: **yes, twice**.
- Proposed shared repair: structured ETB target/grant handling in `events.py`,
  a durable temporary permission/cost representation, and integration with
  `alternative_casts.py` / `costs.collect_cost_options`. Do not “fix” this by
  rewriting Oracle text or directly injecting a permission in this regression.

### 5. Medium, ancillary: Rancor does not return after Tear destroys it

- `test_restart_and_additional.py::test_split_only_affordable_tear_half_resolves_after_snapshot`
- Expected: only the `{W}` Tear half is affordable; it destroys the attached
  Rancor, whose actual graveyard-from-battlefield trigger returns it to hand.[84]
- Actual: half selection, payment, and destruction succeed; Rancor remains in
  **graveyard**, not **hand**, and no return trigger appears in the trace.
- Reproduces on committed main: **yes, twice**.
- Classification: an incidental missing Aura zone-change trigger, **not** a
  split-card cost bug or an undying test. Its assertion was retained rather
  than weakening the final-state expectation to hide it.
- Proposed shared repair: inspect `events.py` permanent-death/self-source
  matching and the return-self effect path. No root-cause fix is claimed.

## Passing controls and meaningful boundaries

- Blaze zero/positive X; negative, absent and unaffordable X rejection.
- Spatial Contortion accepts actual colorless plus generic payment, rejects two
  colored mana without paying or changing state.
- Burning-Tree Emissary red/red, green/green and mixed hybrid payment, followed
  by its actual entry mana trigger.
- Native Firebolt flashback on both seats rejects the normal front cost, pays
  the alternative cost and exiles; Devil's Play covers positive front X and
  zero/positive flashback X with its different colored requirement.
- Burst Lightning base versus kicker payment/damage; Tormenting Voice rejects
  an invalid battlefield discard, pays a real MDFC hand discard, then draws two.
- MDFC front characteristics in library, graveyard targeting and front-face
  restoration; land-face timing and per-turn limit enforcement.
- Adventure instant on the opponent's turn, retained exile permission, rejected
  premature creature casting, then legal creature casting in its own main phase.
- Kolaghan's Command independently handles graveyard/battlefield targets with
  none, one or all targets made illegal; invalid mode count and duplicates reject.
- Common Bond's two target occurrences can affect the same creature twice.
- Real repository SQLite write, writer disposal, fresh engine/session reopen,
  exact snapshot equality, invalid choice actor/min/max rejection and successful
  continuation of a pending modal discard choice.
- Actual `AIAgent(difficulty='master')` decisions in **Aggro and Control**
  diagnostic positions, **both seats**, with at least two legal spells and an
  unaffordable hybrid or true-colorless alternative. Hidden opponent hand
  identities are replaced with another canonical card: the selected action is
  unchanged and decision-making does not mutate the source snapshot. The action
  is checked, paid, resolved, and a second decision is checked without reusing
  the consumed card. These are bounded decision positions, not competitive deck
  templates, round-robin results, or win-rate claims.

An exploratory AI assertion demanded immediate lethal targeting, but the AI
legally spent X=2 killing the opposing Bears instead. That was a **test-policy
error for this legality assignment**, not an illegal action or stall. The final
contract verifies payment/progress/privacy rather than mandating that strategy.
The quality issue is noted for human review, not counted among rules defects.

## Fixture/protocol corrections and remaining gaps

- Initial raw Scryfall-to-factory setup bypassed production hydration and retained
  the combined adventure mana cost. The final offline adapter calls real
  `ScryfallSyncService._normalize_payload` and `hydrate_deck_cards`, then the real
  factory. Adventure payment subsequently passed; no engine defect was filed.
- Initial land-limit setup omitted `last_land_play_turn` and the matching durable
  counter. Corrected consistent state passes. No land-limit defect was filed.
- Snapcaster/granted-flashback+kicker is blocked at the grant, so it is not full
  combination coverage. Alternative-cost-plus-mandatory-discard flashback,
  nonmana flashback prices, arbitrary X-target allocation, and fused split
  casting remain unverified.
- Inspected `costs.py`, `alternative_casts.py`, and the rules-engine tree: no
  delve/convoke implementation was found. Treasure Cruise and Triplicate Spirits
  were fetched for provenance but not presented as supported payment tests.
- Vines of Vastwood is explicitly reported as unsupported kicker. Lava Dart's
  sacrifice flashback and Conflagrate's discard-X flashback have no complete
  confirmed execution contract here. Empty coverage diagnostics for these cards
  are not evidence of support.
- SQLite restart closes/reopens storage in the same pytest process; there is no
  new HTTP/cold-server restart test. No full-suite, deployment or release claim.
- Remand/destination, linked Reanimate life loss, graveyard exile responses,
  Furnace replacement and undying families were not tested or changed.

## Provenance and execution

`fixtures/regression_agent_wave2/cards.json` contains **30 distinct actual
Scryfall printing IDs**, Oracle IDs, complete retrieved payloads, rules URLs,
retrieval timestamps and the actual rulings responses. Retrieval was
2026-10-04 UTC. Some named lookups select preview printings; fixtures preserve
what the service returned rather than inventing identifiers or release dates.
Tests are offline and never populate the playable card cache.

`fixtures/regression_agent_wave2/rules.json` preserves relevant verbatim excerpts
and the source URL for the Wizards **2026-09-25 Comprehensive Rules**, fetched
2026-10-04. Casting/targets, total payment, flashback and kicker expectations are
anchored in CR 601.2, 608.2b, 702.33 and 702.34.[24]

The initial relevant baseline was **147 passed, 70 warnings**, before any new
case was written. Expanded existing-only baseline was **336 passed**. Final
branch and main combined selections each ran twice: **370 passed, 6 failed,
17 warnings** per invocation. Warnings are the existing Pydantic
`datetime.utcnow()` deprecation. There were no collection errors or skips.

All execution used `/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`
read-only. The original source-relative database was not used: confirmed runtime
URL was `sqlite:////home/nick/.hermes/cache/scratch/rules-wave2-q8k52de0/backend/mtg_lab.db`.
An import-time safety gate rejects wave-two collection outside disposable,
non-git source trees below `/home/nick/.hermes/cache/scratch`.

Exact combined test selection (also recorded with absolute cwd, basetemp and
JUnit paths in archive `execution.json`):

```sh
PYTHONHASHSEED=731 PYTHONDONTWRITEBYTECODE=1 \
WAVE2_TRACE=/home/nick/.hermes/cache/scratch/rules-wave2-q8k52de0/final-branch-repeat-1-trace.jsonl \
/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q \
  tests/regression_agent_wave2 \
  tests/test_variable_spell_costs.py tests/test_spell_cost_clauses.py \
  tests/test_multi_target_adventure.py tests/test_modal_spell_faces.py \
  tests/test_split_card_casts.py tests/test_land_and_adventure_faces.py \
  tests/test_kicker.py tests/test_nonmana_kicker.py tests/test_multi_target_modal.py \
  --tb=short \
  --basetemp=/home/nick/.hermes/cache/scratch/rules-wave2-q8k52de0/final-branch-repeat-1-tmp \
  --junitxml=/home/nick/.hermes/cache/scratch/rules-wave2-q8k52de0/final-branch-repeat-1.xml
```

Cwd for that command was the disposable source copy's `backend/`. Repeat two
uses `repeat-2` paths; main uses the extracted committed-main-final copy and
`final-main-repeat-*` paths. For independent reproduction, make a **fresh
`git archive <handoff-commit>` extraction under the scratch root**, then run this
selection from its backend with new output paths. Do not run in either worktree.
Expected exit status is **1** because the six intended regression assertions fail.

## Evidence archive

Archive directory:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/rules-regression-agent-wave2/20261004T211810Z-701cd19-q8k52de0/`

- `execution.json`: exact commands, commits, environment, counts and each node ID.
- `final-*-repeat-*.log` / `.xml`: actual repeated pytest output.
- `final-*-repeat-*-trace.jsonl`: full snapshots, legal moves, announcements,
  payments, rejected candidates, decisions and resulting state.
- All four final trace SHA-256 values are identical:
  `f9f3674efafb56389a417d01ac61195bf53c7cd9f28a11e49ba75b88c5ebb75e`.
- `commit.json`, `owned-files.tar.gz`, `owned-files.patch`, fixture/rules retrieval
  evidence, full Comprehensive Rules, citation ledger, local database backups,
  and Graphify/inspection logs preserve the handoff.
- `SHA256SUMS` and `archive-verification.json` record read-back verification.
  The manifest's own SHA-256 is included in the external handoff.

NFS mount and write/read/delete probe are required before copying; verification
must precede cleanup. Active SQLite was local only. Graphify AST updates ran only
inside disposable source copies; shared worktree graph files were untouched.
The archive contains exploratory failures as well as final evidence so the
fixture corrections are auditable. First-wave scratch was not touched.

## Sources

[24] https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt
[41] https://api.scryfall.com/cards/8f42d773-c742-4465-b6d5-31feaba49146/rulings
[53] https://api.scryfall.com/cards/e90aaa61-3281-4e8f-9eb3-548896d0c14d/rulings
[84] https://api.scryfall.com/cards/named?exact=Rancor
[87] https://api.scryfall.com/cards/22b36ad5-bf4d-436a-9c3c-fa4acd0052fe/rulings
