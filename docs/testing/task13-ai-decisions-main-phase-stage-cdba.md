# AI decisions canonical fixture: main-phase stage

This separate test/data-only candidate is based on immutable
`cdba5196d90b984995718c96a5e2ea8326600b10` plus the frozen r7fyvxdn
canonical-fixture stage. It is **HOLD**, not a green or integration certificate.
The old 153/4 and 158/4 stages remain immutable.

Only the two original lethal-line fixtures receive the approved legal-priority
initial pose: PRECOMBAT_MAIN, active player 1, priority player 1. Their existing
initial pooled red mana remains a trusted policy pose, not naturally tapped mana.
All 94 original names and 180 assertion ASTs remain unchanged. No engine, AI,
cost, deck, move, weight, shared loader, or three-land March test is changed.

The complete two-module roster is 164 cases: the inherited 162 in their exact
order, followed by two funded-UNTAP negative controls. These negatives execute
the real chooser and checked-action rejection without consuming mana or damage.
The inherited positive checked-payment/damage cases are not weakened.

Actual ordinary whole-module runs under the same 300s + 15s pure ceiling:

| Epoch | Passed | Failed | Seconds |
| --- | ---: | ---: | ---: |
| First RED | 158 | 6 | 16.76 |
| Corrected NEW negative message operand, before timing edits | 160 | 4 | 16.67 |
| Approved two timing blocks applied | 160 | 4 | 16.81 |

The first RED includes two NEW negative-test message mismatches: checked_action
rejects the absent legal cast before the later engine untap guard. Only that NEW
message operand was corrected to its actual exact rejection. The original four
failures remain after the timing correction: both original difficulties and
both positive fidelity cases choose pass_priority. Payment and three-damage
tails therefore still do not execute. Further selection cause is unproven; no
additional fixture adaptation or production fix is made.

All seven precollection SQL/socket/process/provider denial canaries passed in
each epoch. There were no unexpected denials, source/runtime changes, database
files, children, extra threads, or FD differences. Full ordered rosters, JUnit,
logs, and before/after maps accompany the private evidence packet.

The qualified executable is
`/home/nick/mtg-deck-testing-lab/backend/.venv/bin/python`, resolving at runtime
to `/usr/bin/python3.12`; sys.prefix is
`/home/nick/mtg-deck-testing-lab/backend/.venv`. The evidence contains the full
2946-file prefix before/after map and actual interpreter identity, not an
environment or credential dump.

This is neither global Task 1.3 closure nor an AI-quality, natural-game, or
native-performance claim. Independent parent review remains pending.
