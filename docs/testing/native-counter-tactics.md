# Native Counterspell Tactics

This is derived from Forge Team/Card-Forge revision
`61e9442c433711a82258daca3236f936a1d6f70e`, GPL-3.0-or-later. The
[source family](../../tools/engine_evaluation/forge/native-ai/counter-tactics/README.md)
includes attribution, license, full upstream source, modified source, patch and
twelve complete canonical programs. It is not a newly trained model.

## Defects And Corrections

The unchanged sixteen-case audit had eight passes and eight strict failures:
six of eight funded, legal Counterspell decisions declined a lethal Bolt, and
both seats missed the lower Bolt below a genuinely paid Vexing Shusher ability.
Paid controls demonstrate the missed saves; manually chosen controls are not AI
successes. The six unfunded, uncounterable and friendly-target controls passed.

Optional counter selection now searches the actual native stack for eligible
opposing targets, with native targeting, counterability, AITgts and
ConditionWouldDestroy checks. A narrowly recognized critical target takes
priority over the first ordinary eligible target. Its selection is used
consistently for targeting, mana value and UnlessCost handling. Only the final
discretionary preference veto is bypassed; earlier refusals, affordability,
backlash and the existing random draws remain. Mandatory/trigger chooser and
payment-method bodies are byte-identical to upstream.

The first draft passed the original sixteen but failed two added internal
protocol cases: after genuine Gilded Light, it still called the retained illegal
Bolt target critical. Native uncountered resolution dealt zero damage. Current
native fizzle-check targeting now precedes the damage forecast.

The next draft passed that correction, but two unchanged Worship controls showed
another forecast limitation: predicted damage was three while actual life loss
was two, leaving one life. A new event-specific public-replacement check now
withholds the critical override for applicable or unresolved visible LifeReduced
effects. It does not force an ordinary decline or implement a complete life-loss
forecast. Both held drafts and their strict failures remain separate evidence.

## Public Information

Both source visibility guards precede inspection of the incoming damage body.
Only a plain literal, targeted DealDamage leaf is considered. Conditions,
compound/optional/triggered forms, unknown amounts, infect and source lifelink
do not gain this override. Life-loss and cannot-lose rules remain relevant.

The new replacement query visits only native static-source zones, never Hand or
Library. Both CardView guards precede replacement inspection. It checks native
zone activity, suppression and applicability; only bounded public literal
selectors and simple battlefield-presence conditions can reach native condition
evaluation. Private zones, defined expressions, dynamic counts and unknown
conditions are not evaluated. No global replacement collector or mutating
replacement execution is called. Native transitive forecasts still do not have
a universal fairness, purity or resolution-completeness certificate.

## Executed Qualification

- The packaged runner independently passed original16, illegal-target2 and
  life-floor2: twenty constructed native rows in three fresh JVMs, 42.014 seconds
  including intake and compilation. All 59,971 declared base resource files and
  pinned inputs matched before/end. This runner's namespace isolation is not
  native SQL-denial instrumentation.
- Separate preservation10 passed, including two actual Oracle/Stifle responses
  and eight exact complete-row comparisons against the unchanged baseline.
  Serialized incoming/ending RNG is included; this is not a global RNG-purity
  claim. Four additional real-state protocol controls passed: no creature for
  own Worship and opponent-controlled Worship must not suppress genuine danger.
- Eight synthetic parameter-map checks passed. They create no game and invoke
  no native applicability/requirements conditions. These are internal contract
  checks, not real-card gameplay or eight additional games.
- Fog16 and Chalice18 preservation passed on the final ten-source/seventeen-class
  prefix. Their original Java programs and expectations remained unchanged.
- All eight fixed-deck/seed natural games completed without error, cap or retry.
  Winners in original/reversed order were Control/Burn, Tempo/Tempo,
  Tribal/Tribal and Tokens/White Weenie; turns were 21/17, 14/13, 10/11 and 15/15.
  All 14,687 event rows and 2,461 actor frames match the preceding target-legality
  revision. Compared with the prior Chalice prefix, six full recorded streams
  match and two diverge; histories are not aligned beyond their first divergence.
  Same winners and completed games are not proof of stronger play.
- All thirty synthetic profile tests pass; all twenty-eight old test methods
  remain unchanged. Schema 8 requires the complete ten-source/seventeen-class
  prefix. Every prior nine-source/sixteen-class payload is unchanged; CounterAi
  is the only new source/class pair. It was independently compiled.

An initial additional-test source accidentally retained diff markers and did
not compile. A separate parameter fixture initially used a UI-only negative card
ID, which omits abilities; it failed before its assertions. Both failures are
preserved, not counted as AI defects. Only new fixture construction was
corrected; original tactical, Gilded and Worship test bytes were not changed.

## Identity And Remaining Work

Final source:
`fa781549b9272dd3b8fc05e80febc9baf470722cb5edce67a2ae4c9e3e423659`.
Independently compiled class:
`baf7d165ef2115d475a29438e9280fcec27b5007228548a4b20dea5852a2b823`.
Prefix content:
`db05b7032887ce9d5b9f769b915f25e9ebdbc04a03f4f8dd4040537d6216f242`.

Private hands, RNG, raw native logs and complete case evidence remain in private
archives on verified NFS. They are not public fixtures. No experimental weights
were trained or installed. General replacement forecasting, arbitrary terminal
abilities, broader playing strength, a new-prefix UI game, live-default adoption,
durable saves, best-of-three acceptance and overall AI RC readiness remain open.
