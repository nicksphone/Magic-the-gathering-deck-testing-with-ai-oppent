# Announced-Source Availability Witnesses

NEW tests/report only. Historical overlap fixtures, tests, report and archives
remain unchanged. Parent owns cast/cost changes; Sagan owns shared mana and
delve forwarding. No engine, mana, costs, AI, importer or live database edits.

## Frozen Inputs And Actual Before/After

Base `d88dbf049209e015f222f9d47d0658e8958c8c01`. Parent's current legacy/public
intent source archive SHA256:
`463e4b2aad69632671bb9dfd18d9ee4cc8875be69212e55b0e2f911cf828aab1`.
Parent's announced-source source archive SHA256:
`678818066e7ad0ef67ddc9c063790aa10dad4e9cd7d1c3f83cd8e5becbdd75a2`.
The engine-only incremental patch SHA256 is
`aea8661ecb604370c2cac7d03f14b54bf00fe13d3cbf651bc1cee3c362371e0f`.
These are immutable local source extractions, not main checkout edits.

The original four source core cases and four HTTP cases run strictly with
`--runxfail`: **8 failed before, 8 passed after the actual parent cast fix**.
The after source contains parent's removal of only those eight xfail marks;
the historical investigator archive was not changed. HTTP changes from 500 to
422 with original spell in hand, full root/controller snapshot and complete
in-memory database dump unchanged for both cards and both seats. Only four
`:memory:` connections occur per HTTP gate; socket connections are forbidden.
Thus those eight cases should be positive regressions in integration.

The NEW positive requirements deliberately contain no xfails:

| Source / experiment | Passed | Failed | Qualification |
| --- | ---: | ---: | --- |
| Current legacy/public intent source | 34 | 36 | Strict before evidence |
| Actual parent cast-source fix | 38 | 32 | Execution rejection fixed; availability not fixed |
| Test-only approved shared-source contract probe | 62 | 8 | Sensitivity experiment, NOT production after-fix evidence |

The contract probe wraps `_spell_payment_plan` in the test process, unioning
the non-null source ID (or supplied card ID) into consumption reservations only
for spell payment. It writes no production source. It does NOT implement or
qualify Sagan's delve forwarding. The actual shared-hook delta still requires
its own strict production replay; the experiment is not substituted for that.
Pure witness gates forbid every SQLite and socket connection; observed attempts
are zero. Independent gates/counts overlap and must not be summed.

## Routes

The actual function is `available_cast_options_and_hints`, not
`get_cast_cost_options`: no latter symbol exists in either pinned backend.
Raw `collect_cost_options` enumerates possible cost definitions, not payability.
Do not turn a raw option's presence into a legal-cast or semantic-support claim.

- `costs.check_cost_option_available` supplies `source_card_id` and
  `cast_resource_card` to `can_pay_with_pool_and_lands`.
- `cast_choice.available_cast_options_and_hints` filters through that check,
  including Aura target-dependent costs.
- `move_generator` uses the filtered options for hand/graveyard, permitted
  library top, selected faces and bestow views. These static routes share the
  same cost check; dynamic tests cover ordinary hand casting only.
- `action_validation` explicit hybrid branch checks also supply source/card
  identity. Actual hybrid/layout cases are not dynamically certified here.
- `AIAgent._can_pay_card_cost` supplies source/card identity; Aura affordability
  instead uses the same target-dependent filtered options.
- `can_pay_with_pool_and_lands` and `auto_pay_cost` both reach
  `_spell_payment_plan`. The approved shared hook is sufficient for these
  identity-bearing source-only witnesses. No duplicate costs/movegen/Aura hooks
  are proposed for source protection.
- `_materialize_action` chooses cost/targets then `choose_resource_payment`.
  For cards without substitution keywords the latter returns without admission.
  Stale canonical intents may therefore materialize; authoritative checked
  admission must reject them atomically. The actual parent cast fix does this.

`callsite-ledger.json` contains 61 exact static call locations/keyword arguments
across the pinned rules/AI files, with source digests. It is a source trace, not
exhaustive runtime, all-layout, trained-competence or full-cost-model proof.

## Residuals Beyond The Shared Source Hook

Two identity-less AI probes remain false positives under the contract experiment:

1. `ai.mana_resource_policy._can_pay` accepts an actual card but forwards name,
   types and text without identity. Familiar plus Village Rites/Cling as the only
   hand card yields a witness funded by discarding the queried spell: four cases.
2. `AIAgent._can_deploy_major_threat` also omits identity. An actual battlefield
   Familiar, a second actual Familiar as the only hand card, four C in pool and
   turn five incorrectly report a deployable threat: two cases.

Minimal AI-owner proposal, only because the shared hook lacks the necessary
input: forward exact instance identity/card view for actual queried spells.
Never infer identity from a card name, invent a future spell, or attach identity
to aggregate color/capacity probes with no actual card. Existing X-sizing probes
also omit identity despite receiving a card; that is static audit scope, not a
canonical X-card reproduction in this handoff. Foretell/Suspend held-answer
checks already supply source identity. Their projected sequencing is not tested.

The last two experimental failures are a distinct additional-cost witness:
canonical Tormenting Voice, Familiar, R in pool and only Voice plus one Island
in hand. Protecting Voice still permits mana production to discard the only
other card, leaving no card for Voice's mandatory additional discard.
`check_cost_option_available` checks discard count and mana independently, so
it remains true. Adding a separate printed Swamp makes a real disjoint payment
possible, and both-seat controls pass. Parent's cast branch correctly refuses
the impossible selected payment; fixing source reservation does not fix this
availability false positive.

Parent cost-owner proposal: a joint all-cost witness must retain fixed announced
IDs, or find a feasible disjoint selection for implicit additional costs, through
mana production. Preserve lawful tap-then-sacrifice and post-mana exhaustive
discard-all/sacrifice-all behavior. This is separate from Sagan's source/delve
seam, not a second source hook or a named-card production patch. No broader
cost-model implementation is proposed without parent ownership/review.

## Canonical Inputs And Reproduction

Requires the prior tests-only overlap patch and its fixture directory
`tests/fixtures/cost_reservation_overlap`. Its 27 unchanged raw public Oracle
records have fixture SHA256
`fd6c5a98c5d88557589f6fa5f7b87dcb33a88be5bff76aa6a316595d1aa1f9ec`.
The source archive is the previously verified September 27 Oracle bulk, SHA256
`17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13`.
The existing per-card Oracle/Scryfall IDs and raw hashes remain unchanged. No
Oracle text, keywords, names, printed mana/stats or fixtures are rewritten.

Rules provenance remains the historical official September 25 CR file, SHA256
`8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`:
601.2a/g/h establish announcement then mana then complete payment. No new
external HTTP, private submission, application startup on a real DB, or SQLite
on NFS occurs. Opt-in local ASGI uses a fresh in-memory database only.

```sh
PYTHONPATH=backend /path/to/external/.venv/bin/python -m pytest -q \
  backend/tests/test_announced_source_availability.py
```

Apply only these two NEW paths after the historical fixture/test dependency.
The test file is investigative: the current source does NOT pass all its positive
requirements. Do not silently mark the remaining failures as correctness or
remove historical known-gap evidence. Requalify Sagan's real shared delta and
any separate AI/cost follow-ups against this same pinned fixture before promotion.
