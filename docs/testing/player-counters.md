# Player counters, scaling and dynamic ward

## Implemented

- A general named player-counter store survives ordinary zone changes, turns,
  planning copies and snapshots. Poison remains authoritative in its existing
  field, so combat and poison loss checks do not split into two counter stores.
  Public views expose the current counters; both human seats render them, with
  runtime validation for counter names and nonnegative integer amounts.
- A registered application-code effect adds counters and emits a shared event.
  Supported Oracle clauses produce actual stack triggers, not immediate gains:
  typed casts/entries, printed mana-value/power thresholds, another controlled
  creature's death, opponent-turn/combat casts and the conditional end-step
  departure family. No card-name dispatch was added.
- Actual battlefield-exit events record which controller had a permanent leave
  this turn, including destruction, exile and bounce. The fact survives snapshots,
  can predate a payoff source entering, and resets only at the next turn. The
  end-step condition is checked when triggering and resolving; a departure after
  the beginning of the end step does not retroactively create that trigger.
- Supported named self and scoped global P/T modifiers scale with the current
  source controller's counters. The global modifier is no longer misread as a
  flat +1/+0 at zero counters. Supported creature P/T characteristic definitions
  also use player counters. Combat, effective views, shared AI valuation and
  layer traces use these results without overwriting printed P/T.
- Ward mana templates whose X is explicitly defined as a named player-counter
  count resolve using the triggered ability's controller and the current count,
  not the spell caster's counters or a chosen casting X. Existing payments,
  responses and human/AI choices apply; human controls show the resolved amount.
- Unknown gain/dependent clauses and player-counter replacement fidelity are
  flagged. A supported clause does not imply a whole card is supported.

## Verification

**2,220 isolated backend tests pass**, with 292 existing deprecation warnings
(175.65 seconds). **181 focused checks pass** across counters, ward, cached
instructions, APNAP events and cleanup. Frontend lint, TypeScript/Vite build,
runtime boundary/unit tests and the complete Chromium harness pass.

Sixty-eight new regressions use fourteen canonical cached card/token rows plus
explicitly labeled malformed-input and core-effect checks. Parser guard tests
do not represent fictional cards or claim additional canonical-card coverage.
The experience-scaled Spirit is the actual Commander 2015 token with Oracle ID
`78adae1b-3c0f-4ded-9303-bb7db1b570a0`, not another token merely named Spirit.
No cards, printed rules or deck balance were invented or modified.

Tests cover both seats, source departure/control, poison compatibility, old
snapshots, planning-copy isolation, turn reset, simultaneous source death,
threshold/timing negatives, effective scaling and dynamic ward. Ten AI style
labels pay a supported beneficial resolved-X removal without mutating the live
decision state. This does not measure strategic strength.

Normal cast/land/turn progression reaches the supported Minthara, Daxos,
Kalemne, Ezuri and Toph clauses for both seats; casting Minthara does not require
a user-chosen casting X. Shared poison addition reaches the existing poison
state-based loss rule. Unparsed X-definition suffixes do not silently pass
preflight, and unknown counter-scaled clauses no longer invent a flat bonus.

The new browser scenario grants experience through the real end-step trigger,
advances the turn, displays experience and effective anthem stats, and lets seat
two pay the resolved ward through HTTP/UI controls. Existing recovery, process
restart, sideboard and natural AI/human BO3 browser flows also pass. New counter
snapshot restoration is directly tested; every counter scenario is not claimed
to have its own full browser restart flow.

Eight seeded seat-paired games across Dimir Control/Tempo, Tokens/Ramp,
Midrange/Drain and Tribal/Burn repeat identical reported game objects and logs
across sixteen executions with no timeout or cast/target rejection. One normal
Spell Pierce optional payment fails. This small offline built-in smoke does not
exercise the entire new card corpus or certify balance or expert play.
[Machine-readable source and check evidence](player-counters.json).

All backend checks ran in disposable source copies with separate SQLite state;
the live database was only read to export canonical fixtures. Installed
dependencies were reused, not freshly installed. Both LAN services respond.

The [read-only cached experience inventory](player-counter-corpus.json) contains
19 public card-data payloads, eight with a recognized gain clause and fifteen
with known gaps. This includes reminder/game pieces and partial cards; an empty
known-gap list is not proof of whole-card correctness. This scoped inventory is
not a complete-corpus rules evaluation.

## Rules References

Ward X is determined during resolution, rather than at triggering, under
[the official 702.21b explanation](https://magic.wizards.com/en/news/announcements/comprehensive-rules-changes-6-1-22).
The controller binding follows the triggered-ability rule in
[Comprehensive Rules 109.5](https://media.wizards.com/2025/downloads/MagicCompRules%2020250919.pdf).
The implementation uses the clarified named self-grant in
[the Foundations Oracle update](https://magic.wizards.com/en/news/announcements/foundations-update-bulletin).
Experience counters belong to players and survive payoff-source departure,
as explained in [Commander 2015 mechanics](https://magic.wizards.com/en/news/feature/commander-2015-mechanics-2015-11-02).

## Known Limitations and Next Upgrades

Player-counter replacements and prohibitions, competing replacement selection,
proliferation/removal/spending costs, energy/radiation payoffs, arbitrary X
definitions, granted conditional ward and full suppression/dependency layers
remain unfinished. Vorinclex/Winding Constrictor player replacements are warned,
not silently declared implemented.

Meren's conditional reanimation, Daxos's counter-defined token creation ability,
Ezuri's variable targeted combat counters, Kelsien's delayed death reward,
Katara's optional draw/discard, Zuko's firebending X and Toph's earthbend X remain
partial. Their working gain/scaling clauses do not close those whole cards.
Maintain explicit warnings until those actual clauses are implemented and tested.

Deeper pre-cast/multi-ward and counter-resource strategy remains open. Long-session
custom-deck/LAN testing still needs human review. The historical optional native
timed-dump crash is not fixed by these passing standard tests.
