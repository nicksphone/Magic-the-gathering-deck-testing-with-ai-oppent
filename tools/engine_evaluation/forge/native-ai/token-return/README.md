# Native Token/Return Planning

This is a modification of the Forge Team/Card-Forge contributors' GPL-3.0-or-later
AI, not an independently authored Magic rules engine. The full native card/token
programs, type system, cost execution, triggers and baseline AI are their work.
See `LICENSE`, `NOTICE`, and upstream commit
`61e9442c433711a82258daca3236f936a1d6f70e`.

`token-return.patch` applies over the preceding twelve-source/twenty-class
sacrifice-cost prefix, plus the pinned upstream `TriggerHandler.java` preimage.
`SOURCE-PINS.json` binds every changed preimage/postimage. No rules bodies change:
the game-side addition is a visibility-only delayed-trigger query. The AI composes
typed token production, resource sacrifice, intrinsic graveyard return and complete
literal life-loss triggers without creating hypothetical cards or copying hands.

The new schema-10 profile contains exactly thirteen sources and twenty-one classes.
The profile builder remains opt-in and does not switch the application runtime.

## Reproduce The Frozen Candidate

```sh
python run.py /absolute/base/BUILD-IDENTITY.json /absolute/parent-prefix \
  /fresh/local/private-output /absolute/candidate-prefix
```

All seven cohorts and all 46 rows are mandatory, with fresh native JVMs under one
shared 300-second budget, 1500 MiB heap and one active CPU each. At most two host
JVMs may exist. The runner verifies the full base resource manifest, exact prefix
payloads, native program bytes, harness inventory, observed class origins, complete
native summaries and input continuity. It uses a network-isolated read-only
namespace; it makes no native-SQL-denial or inherited child-audit claim.

- Oven2 and Goose2 require ordinary AI choices followed by actual paid native wins.
- Negative14 checks refusal to certify nonlethal, wrong-owner, blocked, wrong-token
  and unfunded lines. Other ordinary choices are unjudged; manual controls are not
  AI successes.
- Preference/danger4 includes unforced native sacrifice choices and an opposing
  resource-death trigger that can kill the actor before the return.
- Observer10 and forecast-protocol10 are internal protocol fixtures, not canonical
  card-support claims, natural games, training episodes or expert-play evidence.

The seven Java sources are unchanged from their final separately executed cohorts.
The forecast protocol deliberately changes internal metadata to exercise refusal
boundaries; its modified bodies are not presented as real printed card programs.
`COHORTS.json` is fixture metadata, not proof that this combined runner was executed.

## Boundaries

Only completely admitted public semantics receive a winning-line preference.
Unknown triggers, replacements, relevant statics, unsupported costs, conditional
returns or snow provenance withhold that preference and retain native fallback.
Every admitted sacrifice preference tie is retained; no victim is forced. Possible
resource payments cannot remain credited as surviving payoff sources.

This is not a full-game search, general replacement predictor, nonterminal cycle
valuation, hidden-history certificate or trained/optimal opponent. Current source
visibility does not certify remembered delayed sources that are now hidden.
Natural-game outcomes, application adoption, durable BO3 and broad strategy require
separate evidence. No private game trace is part of this public package.

Paid-copy-token4 uses genuine Rite of Replication tokens: a sacrificed token cannot
return, but it can fund the return of a real graveyard Familiar. Token/clone flags
are observed, never changed by the fixture. Candidate2 gave 2 PASS / 2 RED; the
explicit return-only token guard gives 4 PASS without excluding token payments.
