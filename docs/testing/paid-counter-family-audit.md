# Paid Counter Family Audit

Tests/report only. This is an unsupported-feature ledger, not a qualified product
or a claim that every negative resource validator was reached.

## Exact Source

Frozen activated-ability hint-copy a608 integration:
`a6080522054e806ec76940a1254d1af1842fa81561ef7b6535343fecbd9191f4`.
Candidate tar SHA256:
`1583b49d11d8493283b0db86edca9cf5af4e1a743f102b631a792fec8d664a7e`.
No parent/current/main root was used. No production file was edited.

## Canonical Intake

Both complete JSON fixtures were fetched before offline tests on 2026-10-06.
Raw bytes and acquisition URLs/hashes are in
`backend/tests/fixtures/paid_counter_families/`. Scryfall is the full JSON data
provider, not Wizards. Independently fetched complete official Gatherer HTML
is preserved in evidence:

- [Fertilid official Gatherer](https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=612544&printed=false)
- [Lux Cannon official Gatherer](https://gatherer.wizards.com/SOM/en-us/173/lux-cannon)
- [Fertilid official release notes](https://magic.wizards.com/en/news/feature/commander-legends-release-notes-2020-11-06)

Both activated bodies match the official HTML. No Oracle text is abbreviated,
rewritten, or replaced. Fertilid's filtered search may fail to find, but must
still shuffle; the official release notes confirm this.

## Executed Ledger

New whole module `test_paid_counter_family_audit.py`: **80 PASS, 28 ordinary
strict FAIL**, 42 warnings, 19.73 seconds, exit 1, 600-second bound. No skips,
xfails, exclusions, or production repairs. The 28 failures are desired support
assertions: 4 complete cost admission, 2 Fertilid body compiler, 4 move admission,
2 Lux paid destruction, 8 Fertilid actual search/find-or-decline, 8 actual HTTP
admission. No setup errors remain.

Reachable actual Lux charge-building activation pays a tap immediately, keeps
the stack source/controller, cannot pay the tap twice, then adds exactly one
charge counter through lawful priority passes. Both seats, full snapshot
restart, foreign-owned/controller-retained source, local HTTP memory/file
SQLite, controller recovery, fresh-process file HTTP recovery, and private
information controls pass. There are 20 HTTP rows: 12 controls pass, 8 desired
counter-consuming admissions fail.

Both counter-consuming families fail closed before payment. Actual HTTP rejects
preserve the complete root, controller metadata, and SQL dump. Typed/insufficient,
reserved, wrong-kind, departed, actor/index/target and mana-or-tap negatives are
recorded. Because parsing rejects first, these do NOT independently certify the
later resource/payment checks for these new costs. Initial local logs and test
preimages are retained: first 50/28, expanded 76/32 (four test-setup failures),
then final 80/28. Setup correction compares entire serialized decision views,
including RNG state, instead of Python RNG object identity, and hydrates hidden
canonical alternatives without advancing the gameplay object-ID allocator.
No decision-view fields are excluded.

Retained battlefield boards and mana pools are explicit controlled seams, not
proof of source casting, Fertilid entry counters, theft, or untap episodes.
Paid actions themselves use the real engine and checked_action; no injected
effects, manual emit, or forced execution make desired cases green. Unreachable
Fertilid pending-search/private/restart assertions remain behind strict failed
announcement; they are not qualified by reachable Lux controls.

## Source-Grounded Boundaries and Proposed Ownership

1. `costs.parse_activated_cost` currently full-matches ONLY a standalone fixed
   positive self +1/+1 removal. Both real costs have additional mana/tap parts,
   and Lux also has charge counters. The extractor ALREADY preserves complete
   costs, bodies, and indices; no extractor/regex change is proposed. Minimum
   proposed cost scope is the parser plus a narrow private full-cost helper,
   reusing existing number parsing and restricting accepted complete mana/tap/
   source-counter components. Keep unknown, variable, other-object and trailing
   compound costs rejected. Existing internal ActivatedCost kind/quantity,
   typed validation, reservations, mana staging and incarnation revalidation
   can already represent the two costs. Do not change these without test proof.
2. `move_generator.legal_moves` omits unsupported parsed costs and
   noop bodies. This is correct fail-closed behavior, not the fix site.
3. Fertilid's exact body compiles to `noop` independently of its cost. The
   existing `infer_effect_from_oracle` search branch recognizes searching
   one's own library, not the target-player clause. Proposed separate compiler
   scope: anchored COMPLETE target-player/basic-land/tapped/shuffle grammar,
   producing the existing structured search effect and a validated target
   player. No guessed target or permissive partial body match.
4. `effects.handlers.search_library` currently chooses `state.players[controller]`
   and labels/owns pending choice and placement with controller. Proposed narrow
   handler scope must distinguish ability controller from searching player,
   retain the real cause, route options/private access/entry owner to the target,
   and permit zero findings while still shuffling. Audit pending choice resume
   in `keyword_actions` before requesting changes there; its current call uses
   the choosing player. No current runtime behavior was repaired.
5. Lux's complete destroy body already compiles to `destroy_permanent`; no
   new damage/protection/SBA/target algorithm is proposed. Real paid destruction
   is blocked by cost admission and remains RED.
6. Existing search shuffling directly uses RNG and lacks causal shuffle helper
   dispatch. Closing observer semantics would need narrow retained resolving
   context forwarding in stack/search consumers, not fabricated StackItems or
   source guessing. This is a separate source-observed limitation, NOT a
   measured observer-family closure in this two-family audit.

Product ownership has NOT been granted. A future parser change must separately
adapt old tests that intentionally characterize tap+counter costs as unsupported;
never silently rewrite frozen evidence. Proposed future effect scopes require
coordination with their owners. No schema, API, engine, protection, SBA, legend,
events, AI, deck, or dependency edits are included here.

## Reproduce

Use the verified Python 3.12.3 qualified interpreter and exact requirements pins
recorded in evidence. The offline guard refuses all sockets and any SQLite path
outside the exclusive local source copy. From `backend`, execute:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/backend" \
MTG_ISOLATED_TEST_ROOT="$ROOT" timeout 600 "$QUALIFIED_PYTHON" \
  "$ROOT/evidence/run_guarded.py" tests/test_paid_counter_family_audit.py \
  -vv --tb=short --basetemp="$ROOT/.qualification/audit" \
  --junitxml="$ROOT/evidence/audit.xml"
```

Create `.qualification` first. Expected frozen result is exit 1 with the explicit
28 desired failures. No original 522-case campaign was rerun or relabeled.
