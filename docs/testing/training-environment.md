# Training Environment Groundwork

This is an offline, in-memory deterministic adapter, not a trained neural AI,
expert policy, complete Magic implementation, or training-readiness claim.
Qualification base: `0214bb96`. No scoring, models, database schema, live matches,
canonical deck composition, or card characteristics are changed.

## Boundary

`backend/training/environment.py` wraps the real `MatchFactory` and `RulesEngine`.
`reset(deck_a, deck_b, seed=integer)` accepts existing `BUILTIN_DECKS` names only.
The shipped offline Oracle seed supplies canonical metadata and Scryfall IDs;
missing metadata fails explicitly. These are unchanged lists, not asserted
mechanics-complete or format-legal corpora. No repository, API server, SQLite,
network service, model download, or neural framework is needed.

Both seats request supported mechanic, replacement, and trigger-order choices.
`acting_seat` follows engine choice ownership, pregame declarations, then
priority. Casting retains caster priority until a pass; keeping hands begins at
upkeep. One `step` is one authoritative action, not necessarily a turn or phase.
The environment does not auto-play the other seat or truncate stalled games.

`observe(seat)` goes through the existing `ai.information.decision_view` and then
an explicit JSON allowlist. It includes public zones, authorized known cards,
own hand, public counts/resources, stack declarations, combat, and a pending
choice tag. Legally inspected search/surveil options and remembered observations
remain authorized by that existing boundary. It excludes opposing unknown hand
identities, both unseen library orders/metadata, opposing submitted lists,
private resolution continuations, trace/log history, RNG state, seed, hashes,
and replay snapshots. Prompts are separate from observations. Nonacting seats
receive no prompts; terminal episodes have no acting seat. Returned values are
copies. Python underscore attributes are not a sandbox: give a policy only the
observation/prompts, never the environment's private state or snapshots.

## Actions And Choices

- `prompts()` returns allowlisted engine move/choice **hints**, with conditional
  `required_choices`. They describe source availability, not complete announced
  actions. Nested cost/target hints come from engine-generated authorized views.
- `simple_actions()` returns a checked convenience subset: keep/mulligan/pass,
  land plays/foretell, and already specified replacement/trigger decisions. It
  does not synthesize spell targets, attacks, blocks, payments, or card choices.
  An empty subset is not proof that no legal action exists.
- `lookup(complete_action, seat=None)` returns its canonical ID and normalized
  contract payload, or raises `ActionRejected`. `action_mask(proposals)` tests
  only those proposals; it is not an exhaustive finite action space.
- `encode_action`/`decode_action` use versioned reversible canonical JSON,
  retaining variable-length lists, their order, distributions, nested mode
  targets, faces, and payment selections. Dictionary insertion order does not
  affect IDs. IDs identify payloads, not global vocabulary indices or a specific
  state; revalidate them at every decision. Do not pad/truncate target lists.
- Existing strict `api_contracts.Action` input models reject malformed/extra
  fields. The adapter requires explicit casting cost IDs, applicable X/face/
  hybrid/additional/resource choices, mana colors, and defender assignments.
  Activation discard/sacrifice selections cannot default to a guessed card.
  Engine `checked_action` reuses `validate_action` and real legal-move functions,
  then executes on a copy, including declared-target and resolution checks.
- Engine legacy defaults still define ordinary deterministic mana-source
  autopayment and fixed/self/exhaustive costs. The adapter is not a manual
  mana-payment planner. Mana ability resource/hybrid choices not representable
  in the existing action contract are explicitly rejected as unsupported.
  Other unqualified mechanics may also fail lookup; never infer coverage from
  a contract accepting their shape or from a move hint existing.

`step` publishes state only after checked execution and response construction
succeed. Rejected actions leave cards, RNG, costs, logs, choices, continuations,
and episode counter unchanged. Masks/lookups/observations operate on copies.
No opponent or heuristic fallback is silently selected on a missing choice.

## Rewards And Private Resume Evidence

`step` returns `observation`, per-seat `rewards`, `terminated`, `acting_seat`,
`action_id`, and `steps`. Nonterminal rewards are zero. Actual engine winner
1/2 yields +1/-1; actual engine draw (`winner == 0`) is terminal with zero
reward for both seats. Rewards are terminal-state values, not cumulative reward
shaping; do not sum them repeatedly after termination. Simultaneous losses use
the engine's draw result, not a fabricated winner or win-rate target.

`snapshot()` is a **private** JSON envelope using existing match serializers.
It contains versioned seed/deck/metadata-source provenance, deck hashes, a
content hash of engine/AI boundary/adapter/metadata code and data, deterministic
episode identity, step count, full state including RNG, and a state digest.
Reset with identical lists/seed/content produces identical envelopes; the
factory's random match UUID is replaced only inside this private adapter.

`restore()` verifies version, content/deck/episode provenance, digest, counter,
and exact serializer round-trip before publishing a restored state. A changed
engine/adapter/seed file requires a new episode, not silent replay migration.
Snapshots are trusted local evaluator inputs, not signed or hardened public
uploads. Their hashes detect inconsistencies, not malicious forgeries. Store
them separately from policy inputs and public fixtures. Versioned trajectory
datasets, dataset splits, and training/checkpoint commands are later gates.

## Primitive Consumer

Run from an isolated checkout, with its backend first on `PYTHONPATH`:

```python
from training import TrainingEnvironment

env = TrainingEnvironment()
observation = env.reset('Mono Red Aggro', 'Blue Control', seed=17)
for _ in range(20):  # diagnostic budget, not an engine draw/truncation
    if env.terminated:
        break
    simple = env.simple_actions()
    if not simple:
        print('Explicit choice/action construction needed:', env.prompts())
        break
    preferred = next((item for item in simple
                      if item['action']['type'] == 'keep_hand'), simple[0])
    result = env.step(preferred['id'])
    observation = result['observation']
print(env.rewards)
```

For a spell, use its current prompt's `card_id` and an available
`cost_options[].id`, explicitly construct required `targets`/payments, and call
`lookup` or `action_mask` before stepping. For a mulligan-bottom prompt, construct
`{'type': 'choose_mechanic', 'card_ids': selected_ids}` with exactly the required
count and order. This example is plumbing, not an opponent or learned policy.

## Scoped Qualification

Use main's **existing** external venv; do not install dependencies or copy its
database. Verify installed versions against `backend/requirements.txt` before
claiming gates. The initial system Python exploratory runs were not pin-matched.
The pinned interpreter is
`/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python` (Python 3.12.3); all
eight pinned packages matched at qualification time.

Recorded pinned scoped result: **199 passed in 42.62 seconds**, including
50 adapter tests. This is a scoped regression result, not a full backend gate.

```bash
PYTHONPATH="$PWD/backend" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /home/nick/mtg-deck-testing-lab/backend/.venv/bin/python -m pytest -q \
  backend/tests/test_training_environment.py \
  backend/tests/test_ai_information_boundary.py \
  backend/tests/test_ai_opaque_draw_horizon.py \
  backend/tests/test_mulligan_and_timing.py \
  backend/tests/test_pregame_priority.py \
  backend/tests/test_priority_stack.py
```

New tests cover both-seat hidden-metadata/order invariance, unchanged source
state under queries, exact repeated resets and 60-action seeded trajectories,
mid-mulligan/stack/private-choice snapshots, ordered multiple-mulligan bottoms,
malformed/wrong-seat action immutability, response-failure atomicity, real
Lightning Bolt winners, Consider surveil continuations, real phase/land/priority
behavior, real attacks/blocks, explicit Witch's Oven sacrifice payments, mana
ability color/index legality, actual simultaneous-loss draws, tampered snapshot
rejection, and caller-copy isolation. SQLite/network connections are forbidden
in a state-only smoke test. Tactical positions relocate existing canonical deck
instances; they do not invent gameplay cards or rebalance lists.

Coverage is deliberately scoped. It does **not** qualify every pending kind,
all modal/linked/variable-X/face/cost permutations, effect-casting, replacement
combinations, optional trigger ordering, library-search ordering, or every card
in a named list. The observation allowlist is not yet a lossless feature set
for every public rule/resource. Action IDs describe payloads, not validated
strategic equivalence classes. Masks execute copies and are not optimized for
large candidate sets. No learned-policy quality, full-match completion rate,
throughput target, neural readiness, expert-data quality, or evaluation win-rate
gate has been claimed. Add real canonical fixtures and invariant tests before
expanding any declared supported training corpus.

## Integration And Storage

The integration patch owns only `backend/training/`,
`backend/tests/test_training_environment.py`, and this document. It applies to
the pinned base without modifying engine/AI/model/schema files. Requalify on a
new main revision before integration; there are no main/candidate writes here.

Completed patch, dependency audit, test logs, refreshed AST graph, scope manifest,
and checksums are archived beneath
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/training-groundwork/` after
verifying the NFS mount and write access. Active checkout and test scratch remain
local; no live SQLite database is used or placed on NFS. Graph refresh output is
kept out of the integration patch to preserve the new-file ownership boundary.
