# Counter prohibitions

## Implemented Scope

One application-code placement helper enforces supported **unconditional**
Oracle prohibitions, without card-name dispatch:

- Players, source controller or opponents cannot get all/named counters.
- Listed permanent types cannot receive counters; any listed type in a
  multitype permanent applies. Planeswalker-only permanents are not covered by
  Solemnity's printed type list.
- A source cannot receive counters itself, or its controller's creatures cannot
  receive the named P/T counter kind.

The helper covers shared permanent/player effects, infect/wither/toxic damage
consequences, supported Soul-Scar-style noncombat damage replacement, token
creation/Incubate, supported Escape/delayed/X spell-entry counters, opening-hand
entry counters and Saga advancement. Poison, lore and loyalty retain their
authoritative legacy fields. Counter gain events are emitted only when actual
player counters were placed. Existing counters are never removed by a ban.

Internal marked-damage, prevention, temporary-stat and animation flags are not
physical counters. Banning infect/wither counters does not convert damage to
ordinary life loss or marked damage, and does not prevent damage/lifelink.
Toxic still causes ordinary damage life loss when its poison counters are
blocked. A separate land-animation instruction still happens even when its
counters cannot be placed. Ordinary positive loyalty costs are filtered/rejected
when the current permanent types prohibit placement; zero and removal costs
are not placement.

Standalone-static parsing excludes reminder text, quoted abilities, unresolved
activated/triggered instructions and unsupported conditional clauses. Cached
instructions contain no mutable state. Detected unimplemented prohibition text
is explicitly reported by the existing known-gap diagnostics.

## Validation

**2,264 isolated backend tests pass**, including **44 new regressions** and
**118 focused checks**. Existing deprecation warnings remain (292); the final
full run took 186.58 seconds. Frontend lint, TypeScript/Vite build and unit
contracts and the full Chromium harness pass, including natural AI, human-vs-AI
and human-vs-human BO3, recovery and sideboarding. Verification results and source fingerprints are recorded in
`counter-prohibitions.json`. Canonical fixtures
come from a read-only query of the existing card knowledge database, with printed
Oracle text/types/stats preserved. Malformed-parser negative tests are labeled
and are not playable or claimed canonical cards. All runtime tests use disposable
source/database copies, not the user's live match database.

Eight seeded seat-paired smoke games (Dimir Control/Tempo, Tokens/Ramp,
Midrange/Drain and Tribal/Burn) ran twice with identical complete reported
game/log objects, no timeout and no detected cast/target/cost rejections.
These are repeatability checks, not statistical balance or expert-AI evidence.

A direct probe ran against actual parent revision `42c97ab` and the updated
engine, using the same canonical cards with Solemnity on the battlefield:

| Result | Parent (incorrect) | Updated |
| --- | ---: | ---: |
| Experience counters gained | 2 | 0 |
| Poison counters from infect | 3 | 0 |
| Creature -1/-1 counters from infect | 3 | 0 |
| Incubator entry +1/+1 counters | 4 | 0 |
| Saga lore counters added | 1 | 0 |

This is a focused rules comparison, not a broad AI or whole-card certification.

## Known Limitations and Next Upgrades

- Multiplication, halving, additive replacements, affected-player ordering,
  placer-versus-recipient attribution and resumable competing counter packets
  are not implemented by this helper. Existing replacement warnings remain.
- General counter placement on entry, returned/copied permanents, initial
  planeswalker loyalty, arbitrary additional/activation costs and battle defense
  need a full placement-path audit. Wiring supported entry paths does not certify
  every battlefield-entry replacement or its ordering.
- Conditional/turn-limited bans, including poison caps followed by a turn ban,
  remain unsupported and warn. Complete ability suppression/layer dependencies
  remain a separately documented engine gap.
- Proliferation, counter spending, arbitrary counter-added triggers and deeper
  counter-resource AI strategy are unfinished. No broad AI-strength or deck-balance
  claim follows from the smoke games or these rule regressions.

Rules references: Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules),
[infect mechanics](https://magic.wizards.com/en/news/feature/mirrodin-besieged-mechanics)
and [toxic mechanics](https://magic.wizards.com/en/news/feature/phyrexia-all-will-be-one-mechanics).
