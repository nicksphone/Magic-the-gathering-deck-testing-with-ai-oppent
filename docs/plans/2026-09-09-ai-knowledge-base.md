# AI Quality + Knowledge Base Implementation Plan

## September 27 implementation status

The historical baseline below describes September 9 only. Canonical ingestion now supports all unique Scryfall Oracle cards via `scripts.sync_all_card_knowledge`, plus individual/corpus rulings verification via `scripts.sync_corpus_cards` and coverage reporting via `scripts.knowledge_gap_report`. The first local bulk import added 38,690 records, including 6,433 faces and 504 disambiguated same-name Oracle variants. Bulk metadata is not a gameplay-support certificate and does not include verified rulings until separately fetched. Successful empty ruling lists are valid; do not require every card to have published rulings. The existing AI does not yet consume persisted knowledge, and verified seed replacement, tactical profiles and sideboarding remain unfinished. See the current root `plan.md` for release priorities.

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Raise AI decision quality by replacing hand-written heuristics with a verified, corpus-wide knowledge base, and close every known card-data gap in the shipped deck corpus.

**Architecture:** A new `backend/knowledge/` package becomes the single source of card knowledge: verified card data (auto-synced from Scryfall, never hand-maintained), per-card tactical profiles (play value, threat level, removal answerability, cast windows), and matchup profiles derived from seeded round-robin results. The AI agent reads these instead of substring-matching oracle text or using hardcoded weights. The existing replay-priors pipeline stays and gains matchup context.

**Tech Stack:** Python 3.12, SQLModel/SQLite (`backend/mtg_lab.db`), Scryfall API (existing `get_with_backoff`), httpx, pytest.

**Verified baseline (2026-09-09, commit 57bcc84):**
- `pytest -q` → **567 passed** in ~115s. This is the gate after every task.
- `python3 -m scripts.oracle_corpus_report` → corpus of 81 unique cards / 3,780 copies: 0 `parser_fallback`, 0 `missing_oracle`, 184 `static_or_noop` (lands/tax cards, expected).
- `backend/mtg_lab.db` (the active DB): 91 cards cached, **91/91 with empty `rulings_json`**, 2 blank oracle texts.
- Fallback coverage: 75/81 deck cards; uncovered: **Lava Spike, Lightning Bolt, Mountain, Rift Bolt, Sacred Foundry, Skewer the Critics**.
- `backend/ai/data/log_priors.json`: 81 cards from 2,767 games / 1.32M trace lines; consumed only by `AIAgent._historical_cast_timing_bias` (agent.py:1497), capped at ±0.8 score with a `casts >= 6` threshold.
- `matchup_profiles.py` is 44 lines of hardcoded if/elif weights.
- AI never sideboards (no sideboard logic in `backend/ai/`).
- Scryfall spot-check proved hand-written fallback texts have drifted (examples: Soul-Scar Mage tax text, Village Rites missing cost, The Meathook Massacre name/cost, Ugin loyalty set, Torrential Gearhulk exile clause, Cauldron Familiar "target" vs "each", Hydroid Krasis counters clause).

**Out of scope (YAGNI):** learned/RL policies, LLM-assisted play, new UI beyond existing panels, rules-engine changes (this plan is data + AI only; rules fixes stay in plan.md), sideboarding UI.

---

## Phase 0 — Baseline + measurement (must land first)

### Task 0.1: Baseline gate script
**Objective:** One command that records the metrics every later phase moves, so "AI is better" is provable, not asserted.

**Files:**
- Create: `backend/scripts/baseline_report.py`
- Test: `backend/tests/test_baseline_report.py`

**Step 1:** Run and record baseline:
```bash
cd backend
./.venv/bin/python -m scripts.oracle_corpus_report --out /tmp/kb-baseline-oracle.json
./.venv/bin/python scripts/ci_regression_gate.py --matches-per-pair 2 --max-decks 6 --out /tmp/kb-baseline-gate.json
```
**Step 2:** `baseline_report.py` reads those artifacts + `backend/ai/data/log_priors.json` + the card-play analytics JSONL of the gate run and prints a single JSON blob: win rates per archetype pair (with Wilson CI via existing analytics code), timeout/stall counts, invalid-target/cost-failure counts, per-archetype decision-quality counters (missed land drops, unused-mana passes, lethal misses — fields already in traces), oracle status counts, card-cache completeness.
**Step 3:** Test: report runs on the baseline artifacts and contains all keys (use fixtures, no network).
**Step 4:** Commit. Save the baseline blob to `docs/plans/baselines/2026-09-09-pre.json`.

**Acceptance:** `baseline_report.py` output is stable across two runs on the same artifacts (deterministic).

### Task 0.2: Decision-quality metric export
**Objective:** Persist per-matchup decision-quality counters so Phase 4 can A/B compare.

**Files:**
- Modify: `backend/analytics/` (batch summary writer — add `decision_quality` block reusing existing counters)
- Test: extend existing batch-analytics test

**Step 1:** Failing test: batch summary JSON contains `decision_quality` with `missed_land_drops`, `unused_mana_passes`, `lethal_misses`, `bad_blocks`, `stall_streaks` per deck and overall.
**Step 2:** Implement by aggregating counters already emitted in AI traces (do not invent new trace fields).
**Step 3:** Commit.

**Acceptance:** gate run summaries include the block; existing 567 tests still pass.

---

## Phase 1 — Knowledge base core (data layer)

### Task 1.1: `CardKnowledge` model + repository
**Objective:** Typed, persisted per-card knowledge separate from display metadata.

**Files:**
- Create: `backend/knowledge/__init__.py`, `backend/knowledge/models.py`
- Modify: `backend/persistence/db.py` (schema), `backend/persistence/repository.py` (upsert/query)
- Test: `backend/tests/test_knowledge_models.py`

**Step 1:** Failing test: `CardKnowledge` row round-trips via SQLModel with fields:
```python
name            # unique, normalized
scryfall_id     # provenance
oracle_source   # "scryfall" | "manual" (never "fallback" — fallbacks get deleted in 1.3)
play_value      # float 0-10, None until profiled
threat_level    # int 0-3, None until profiled
answerable_by   # json list[str] of effect keys (e.g. ["destroy_target","exile_target","counter"])
cast_windows    # json list[str] ("instant_window","main_phase","combat")
etb_impact      # float, expected board swing from entering
profiles        # json blob (Phase 3 output)
updated_at
```
**Step 2:** Implement model + `upsert_card_knowledge` + `list_card_knowledge(names=None)`.
**Step 3:** Commit.

### Task 1.2: Bulk Scryfall sync for the corpus
**Objective:** Every card in the shipped corpus (builtin + expansion + all deck records) gets real Scryfall data in `cardcache` and a `scryfall`-sourced `CardKnowledge` row. No hand-written card data survives.

**Files:**
- Create: `backend/scripts/sync_corpus_cards.py`
- Reuse: `card_data.sync.ScryfallSyncService`, `scripts/oracle_corpus_report.collect_corpus()`
- Test: `backend/tests/test_sync_corpus.py` (monkeypatch httpx; no network in tests)

**Step 1:** Failing test: with a fake client, `sync_corpus_cards` requests `api.scryfall.com/cards/named?fuzzy=<name>` for each distinct corpus name, upserts cache + knowledge, records failures without aborting, and is idempotent (second run: 0 requests for already-complete cards).
**Step 2:** Implement with existing `get_with_backoff` rate-limit handling; respect Scryfall's 5 req/s (sleep 0.25s between requests). Fetch rulings via `rulings_uri` **and persist them** (this fixes the 91/91 empty-rulings gap).
**Step 3:** Run for real: `./.venv/bin/python -m scripts.sync_corpus_cards` — expect ~81 requests, ~9s. Verify with:
```bash
python3 -c "import sqlite3; con=sqlite3.connect('mtg_lab.db'); print(con.execute(\"select count(*) from cardcache where rulings_json in ('','[]')\").fetchone())"
# expect: (0,)
```
**Step 4:** Commit (data files are gitignored; commit only code).

**Acceptance:** 81/81 corpus cards cached with non-empty oracle text and rulings; `oracle_corpus_report` still shows 0 fallback/missing.

### Task 1.3: Delete hand-written fallbacks, replace with verified seed file
**Objective:** Kill the drift-prone `FALLBACK_CARD_DATA` dict.

**Files:**
- Delete: `backend/card_data/fallback_cards.py`
- Create: `backend/card_data/seed_cards.py` (generated snapshot, 81 cards, committed — used only when offline)
- Modify: every import of `fallback_card_payload` (service.py, sync.py, oracle_corpus_report.py, hydration.py, display.py — grep `fallback_card`)
- Test: update existing fallback tests to use the seed file

**Step 1:** Generate the seed from the live cache:
```python
# one-time: dump cardcache rows for the corpus names into seed_cards.py as a dict literal
```
**Step 2:** Failing test: offline simulation (no network) still hydrates all corpus decks from `seed_cards` with identical oracle text to the cache.
**Step 3:** Replace all call sites; delete `fallback_cards.py`; fix tests.
**Step 4:** Full `pytest -q` (gate: 567+ pass, no fallback-name references left: `grep -rn fallback_card backend --include='*.py'` returns only seed/seed-derivative hits).
**Step 5:** Commit.

**Acceptance:** zero hand-maintained oracle text in the repo; offline startup works from committed seed.

### Task 1.4: Knowledge completeness gate
**Objective:** Make "knowledge base is complete for the corpus" a checkable, CI-visible fact.

**Files:**
- Create: `backend/scripts/knowledge_gap_report.py`
- Test: `backend/tests/test_knowledge_gap_report.py`

**Step 1:** Failing test: report lists every corpus card with: cached?, knowledge row?, rulings count, image local?, `oracle_source` — and exits non-zero if any corpus card lacks a `scryfall`-sourced knowledge row.
**Step 2:** Implement (reuses `collect_corpus` + repository).
**Step 3:** Run: expect exit 0 after Task 1.2. Add the command to README Diagnostics.
**Step 4:** Commit.

**Acceptance:** `knowledge_gap_report.py` passes on the committed corpus; fails loudly when a new deck references an unsynced card (test by temporarily adding a fake name to a copy of a builtin deck fixture).

---

## Phase 2 — Card tactical profiles (the "knowledge" the AI actually uses)

### Task 2.1: Profile derivation rules
**Objective:** Deterministic, testable per-card tactical facts derived from structured card data + rules-engine metadata — not LLMs, not vibes.

**Files:**
- Create: `backend/knowledge/profiles.py`
- Test: `backend/tests/test_knowledge_profiles.py`

**Step 1:** Failing tests for each derivation (each is a small pure function):
- `play_value(card, corpus)`: base from mana curve position within its archetype (reuse `ai/deck_analysis._cmc`/`analyze_deck`), + trigger-engine bonus (reuse `_spell_tags`-equivalent structured detection on `AbilitySpec`, **not** card names), + payoff density (tokens/draw/PT per clause, parsed from `EffectSpec` clauses).
- `threat_level(card)`: 0 = land/blank, 1 = 1-drop/interaction, 2 = big threat (MV≥4 or sweep/ETB swing ≥4), 3 = game-ender (win condition, sweep, mill, life drain).
- `answerable_by(card)`: effect keys from the rules engine's effect registry (`effects/registry.py`) whose target class matches this card's type line + keywords (destroy/exile/counter). Hexproof/shroud/indestructible/uncounterable reduce the set (reuse `rules_engine/protection.py` predicates).
- `cast_windows(card)`: from card type (instant → both windows, sorcery → main, creature → main+combat-via-haste check).
**Step 2:** Implement; every function takes `CardInstance`/metadata dicts, no card-name branches.
**Step 3:** Property test: running profile derivation over all 81 corpus cards produces no exceptions and writes 81 `CardKnowledge` rows via `upsert_card_knowledge`.
**Step 4:** Commit.

**Acceptance:** `python3 -m scripts.sync_corpus_cards --profile` (new flag, calls `profiles.py`) fills `play_value`/`threat_level`/`answerable_by`/`cast_windows` for 81/81 cards; unit tests pin at least 10 known-correct values (e.g., Supreme Verdict threat_level 3 + answerable_by excludes counter for "can't be countered"… note: SV's uncounterable text only applies in the real card; pin against seed data).

### Task 2.2: AI consumes profiles (replace `_spell_tags`)
**Objective:** Agent scoring reads `CardKnowledge` instead of substring-matching.

**Files:**
- Modify: `backend/ai/agent.py` — replace `_spell_tags` (line ~1620) with `knowledge_tag_lookup(card_name)`; update `_cast_bias`, `_block_bias`, `_choose_x_value` call sites to receive tags from the knowledge layer
- Test: `backend/tests/test_ai_knowledge_tags.py`

**Step 1:** Failing tests:
- `_spell_tags`-equivalent output for Soul-Scar Mage no longer depends on its name (rename the card in a fixture → same tags).
- A card with "bolt" in its name but no damage text does not get the `burn` tag (the old code's literal bug: `any(k in text for k in ["bolt","spike","shock","lava"])`).
- Knowledge layer missing a card (offline, unsynced) → agent falls back to current `_spell_tags` behavior **and logs an `oracle_fallback`-style counter** so gaps are visible in analytics (do not silently degrade).
**Step 2:** Implement: `backend/knowledge/service.py` with `tags_for(name) -> set[str]` backed by `CardKnowledge.profiles`, cached in-process (same pattern as `AIAgent._log_priors_cache`).
**Step 3:** Full pytest gate + one head-to-head smoke:
```bash
python3 scripts/debug_head_to_head.py --deck-a Tempo --deck-b "Blue Control" --matches 1
```
Expect: completes, 0 invalid targets.
**Step 4:** Commit.

**Acceptance:** `grep -n "bolt\|spike\|shock\|lava" backend/ai/agent.py` returns no tag-branch hits; smoke run clean.

### Task 2.3: Threat-aware blocking/removal using `answerable_by` + `threat_level`
**Objective:** Make the AI's most visible weakness (bad blocks, removal misfire) profile-driven.

**Files:**
- Modify: `backend/ai/agent.py` — `_choose_blocks` (~2175), `_block_bias` (~1163), `_cast_bias` removal branch
- Test: `backend/tests/test_ai_threat_blocking.py`

**Step 1:** Failing tests:
- Against a 7/7 with deathtouch, AI prefers blocking with its biggest creature even when a smaller creature "wins" on raw PT (threat_level 3 override).
- Removal spell scoring: with a threat_level 3 target in play, `destroy_target`-capable spells rank above value cards; with only threat_level 0/1 targets, they rank below.
- A hexproof 4/4 is not targeted by `answerable_by`-destroy effects (existing target validation already enforces legality — this pins that AI *choosing* also avoids it pre-validation).
**Step 2:** Implement using `knowledge.service.tags_for` + `threat_level`; keep existing search-based block logic, only change the *scoring inputs*.
**Step 3:** Full pytest gate + gate-run A/B: rerun Task 0.1 baseline command; `bad_blocks` and `lethal_misses` counters must not increase vs baseline (record in `docs/plans/baselines/2026-09-09-post-p2.json`).
**Step 4:** Commit.

**Acceptance:** A/B counters non-regressed; the three failing tests now pass.

---

## Phase 3 — Matchup knowledge (replace `matchup_profiles.py` with learned data)

### Task 3.1: Seeded round-robin runner with decision traces
**Objective:** Machine-readable matchup evidence: win rates AND decision-quality per pair.

**Files:**
- Create: `backend/scripts/matchup_round_robin.py` (wraps existing batch simulator: all builtin archetype pairs, best-of-3, fixed seeds, max tick cap)
- Reuse: `ci_regression_gate.py` deck selection, `analytics` batch pipeline
- Test: `backend/tests/test_matchup_round_robin.py` (2 decks, 1 game, fake seed — verifies JSON schema)

**Step 1:** Failing test: output JSON has `pairs[].{deck_a, deck_b, seed, wins_a, wins_b, timeouts, decision_quality_a, decision_quality_b, win_rate_ci}`.
**Step 2:** Implement (delegates to existing batch sim; adds nothing to the engine).
**Step 3:** Run full: all builtin pairs × best-of-3 (background, notify; expect 10-30 min on this box).
**Step 4:** Commit runner + save output to `docs/plans/baselines/matchup-2026-09-09.json` (committed — it *is* the knowledge artifact).

### Task 3.2: Learned matchup profiles
**Objective:** `profile_for()` returns data-derived biases.

**Files:**
- Modify: `backend/ai/matchup_profiles.py` — keep signature `profile_for(own, opp) -> dict[str, float]` (call sites unchanged); body loads a generated `matchup_profiles.json` and falls back to the current hardcoded table for unknown pairs
- Create: `backend/scripts/derive_matchup_profiles.py` (round-robin JSON → per-pair proactive/holdup/risk deltas from win rate + decision-quality gaps, clamped, deterministic)
- Data: `backend/ai/data/matchup_profiles.json` (committed artifact)
- Test: `backend/tests/test_learned_matchup_profiles.py`

**Step 1:** Failing tests:
- Derive: pair with 70% win rate + opponent's `holdup_bias`-related misses → generated profile has nonzero `proactive_bias` for the winner's archetype against that opponent.
- Load: unknown pair → exact values of the old hardcoded table (no behavior regression for out-of-corpus archetypes).
- Determinism: two derive runs on the same input → byte-identical JSON.
**Step 2:** Implement; run derive on Task 3.1 output; commit artifact.
**Step 3:** Full pytest + baseline A/B (same command as 2.3) → `docs/plans/baselines/2026-09-09-post-p3.json`; overall stall/timeout count must not increase.
**Step 4:** Commit.

**Acceptance:** `matchup_profiles.json` covers every builtin archetype pair; A/B non-regressed; unknown-pair fallback pinned by test.

### Task 3.3: Enrich replay priors with matchup context
**Objective:** `log_priors.json` gains per-card timing *by opponent archetype*, and the agent uses it.

**Files:**
- Modify: `backend/ai/log_priors.py` (`_build_priors_payload` adds `opponent_archetypes` breakdown; builder reads `opp_archetype` from trace lines — already present in AI TRACE JSON)
- Modify: `backend/scripts/build_ai_log_priors.py` (pass through)
- Modify: `backend/ai/agent.py` `_historical_cast_timing_bias` (1497): consult the opponent-archetype row when available, else the aggregate row (backward compatible)
- Test: `backend/tests/test_log_priors_archetype.py`

**Step 1:** Failing test: fixture traces with two opponent archetypes produce separate timing rows; agent bias uses the matchup row when `opponent_archetype` is set.
**Step 2:** Implement; rebuild priors from existing `training_runs/` exports (offline, no new games needed for the first cut):
```bash
./.venv/bin/python -m scripts.build_ai_log_priors
```
**Step 3:** Full pytest gate; commit (rebuild `log_priors.json`).

**Acceptance:** `log_priors.json` contains `opponent_archetypes` for cards with ≥3 casts in ≥2 archetypes; agent test passes.

---

## Phase 4 — AI upgrades built on the knowledge base

> Order matters: every item here consumes Phase 1-3 data. No item may add card-name branches (that's the regression this plan exists to prevent).

### Task 4.1: Lethal/completion-line detection (knowledge-driven)
**Objective:** AI reliably finds and executes lethal; this is the #1 measurable "bad AI" complaint.

**Files:**
- Modify: `backend/ai/endgame_policy.py` (existing file — extend)
- Test: `backend/tests/test_ai_lethal_detection.py`

**Step 1:** Failing tests (build with existing `_setup_creature` helpers):
- 5/5 attacker + 1/1 first-strike vs 7-life opponent with no blockers → AI attacks (lethal).
- Opponent has 4 life, AI has `deals x damage` instant in hand, can pay X=4 → AI casts at lethal X, not X=1.
- Lethal requires an answerable_by-destroy removal on a blocking 3/3 → AI plays removal then attacks on the same turn when sequencing allows.
**Step 2:** Implement: `_find_lethal_line(state)` enumerates: total unblocked power (reuse `_effective_combat_stats`), instant-window damage spells (tags from knowledge layer), X-value from `_choose_x_value` with a `lethal_target=opp_life` override, and one-step removal sequences. Bounded: ≤4 candidate spells, no full search.
**Step 3:** Full pytest + A/B: `lethal_misses` counter must drop vs `2026-09-09-post-p3.json` (record post-p4).
**Step 4:** Commit.

### Task 4.2: Interaction-hold policy from knowledge
**Objective:** Control/counter decks stop over-passing (the "hold-up pass" cluster in anomaly diagnostics) and stop over-casting into developed boards.

**Files:**
- Modify: `backend/ai/agent.py` `_should_hold_up_interaction` (~1030), `_pass_bias` (~985)
- Test: `backend/tests/test_ai_hold_policy.py`

**Step 1:** Failing tests:
- Control deck, opponent casts a threat_level 3 spell → counter is played (not held).
- Control deck, opponent casts a 1/1 (threat_level 1), counter available, board stable → holding (pass) scores above casting.
- Opponent has a known unanswerable-by-counter threat (uncounterable tag) → counter not wasted on a castable-but-wrong target when a removal answer exists (`answerable_by` lookup).
**Step 2:** Implement using `threat_level` + `answerable_by` of the *top stack object* (target metadata already exists in legal moves — no engine change).
**Step 3:** A/B: `unused_mana_passes` and unexplained `pass_priority` cluster counts must drop; timeout count must not rise.
**Step 4:** Commit.

### Task 4.3: Card play ordering from `play_value`
**Objective:** Main-phase sequencing (land → 1-drops → curve) driven by profile data.

**Files:**
- Modify: `backend/ai/agent.py` `_rank_moves`/`_cast_bias` cast-timing section
- Test: `backend/tests/test_ai_play_ordering.py`

**Step 1:** Failing tests:
- Two-castable-turn: 3/3 (MV2) + sweeper in hand → sweeper held if board has no threat_level ≥2 target, played if it does (replaces hardcoded sweep logic with threat-driven).
- Mana dorks play before other 1-drops when untapped lands < 3 (curve pressure from hand profile, existing `_current_hand_profile`).
**Step 2:** Implement: sort key blends `play_value`, `threat_level` of what the card answers, and existing cast bias; clamp so no single profile field dominates (max contribution 1.5 score units — keeps replay priors and matchup biases meaningful).
**Step 3:** A/B: `missed_land_drops` and `unused_mana_passes` non-increased; overall win-rate spread across archetypes non-increased (no archetype collapse).
**Step 4:** Commit.

### Task 4.4: Sideboard plan generator (knowledge-based, minimal)
**Objective:** Between games, the AI swaps in cards whose `answerable_by`/tags match the opponent's actual board, and swaps out cards that were dead.

**Files:**
- Create: `backend/ai/sideboard_policy.py`
- Modify: `backend/main.py` match-controller game transition (call point exists where `apply_sideboard_swaps` is already imported at line 33)
- Test: `backend/tests/test_sideboard_policy.py`

**Step 1:** Failing tests (pure function `plan_swaps(my_deck, opp_deck, game_events) -> list[swap]`):
- Opponent ran a 6-creature tribal game → plan swaps in a sweeper from sideboard (tag `sweeper`) for a 4-drop that never cast (event log: never left hand).
- Plan is bounded to ≤3 swaps, never removes a card that was lethal-contributing in game events, always keeps deck at 60.
- No sideboard → returns empty, no error.
**Step 2:** Implement using knowledge tags + game-event facts (cards played/died — both in replay lines); wire into match transition with an `auto_sideboard` flag defaulting ON for AI seats.
**Step 3:** Full pytest + best-of-3 smoke (Tempo vs Blue Control, both with sideboards): game 2+ boards differ from game 1 board and are legal (60 cards, no duplicates beyond 4).
**Step 4:** Commit.

**Acceptance:** smoke BO3 shows ≥1 swap in ≥1 game of 3; deck legality validated.

### Task 4.5: A/B tuning round on decision-quality metrics
**Objective:** Use the Phase 0 metrics to tune the few remaining scalar weights — with evidence, not guesses.

**Steps:**
1. Run full matchup round-robin (Task 3.1 command) → `post-p4.json`.
2. Diff every counter vs baseline; for any archetype pair where win rate moved >15pts or a decision-quality counter regressed, open a focused issue-style note in this file with the specific counter and the trace excerpt.
3. At most 3 weight adjustments total, each behind its own test that pins the new behavior, each followed by a full pytest gate.
4. Final artifacts: `docs/plans/baselines/2026-09-09-post-p4.json` + one-paragraph per-metric delta summary appended to this plan.

**Acceptance criteria (plan-level Definition of Done):**
- All 567+ existing tests pass (plus ~40 new) after every phase.
- `knowledge_gap_report.py` exits 0.
- Final A/B vs `2026-09-09-pre.json`: `lethal_misses` down, `bad_blocks` down, timeouts flat-or-better, no archetype pair regressed >15pts.
- `grep -rn "fallback_card\b" backend --include='*.py'` → zero hits; zero card-name string branches in `backend/ai/` tag logic.
- README AI section + plan.md "AI quality" section updated to match reality; `graphify update .` run after.

---

## Rollback points
- Each task = its own commit; revert per-task with `git revert <sha>` without breaking gates.
- Phase boundaries are clean: Phase 1 (data) can ship independently; Phase 2/3/4 each fall back to prior behavior via the knowledge layer's explicit fallback counters — if profiles cause regressions, disable by setting `profiles={}` in `CardKnowledge` rows (agent then uses the pinned legacy paths).
- `backend/mtg_lab.db` is gitignored: before Task 1.2's real sync, copy it to `mtg_lab.db.bak-<date>`; seed file (Task 1.3) is the offline safety net either way.

## Risks
1. **Scryfall rate limits / outages** during Task 1.2 → mitigated by existing backoff + idempotent reruns; seed file keeps app functional offline.
2. **A/B noise** — best-of-3 samples are small for win-rate claims; Wilson CIs already in analytics; decision-quality counters (not win rates) are the primary acceptance signal, and they are deterministic given seeds.
3. **Profile quality** — derivations are heuristic-by-construction; pinned value tests (Task 2.1 Step 4) bound how wrong they can be, and the fallback counters make silent degradation impossible.
4. **Scope creep toward learned policies** — explicitly out of scope; the priors pipeline stays statistical.
