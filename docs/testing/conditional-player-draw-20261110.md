# Conditional player draw

The complete-clause compiler supports the five colors, monocolored,
multicolored and colorless qualities. At resolution, the resolver checks current
battlefield membership, controller, effective creature type and state-aware
colors. It selects each eligible player once and delegates ordinary draws to
the existing sequences in active-player order.

Draw restrictions, replacements and continuations retain their normal behavior.
A qualifying draw must finish, including paused replacement choices, before a
following creature wipe proceeds. Rules 105.2a–c, 608.2c, 608.2h and 121.2c
describe the relevant color and resolution semantics.

The regression scenarios cover current and restored states, duplicate and
mixed-color boards, removal before the wipe, control changes, supported color
conversion, noncreature/colorless exclusions and both players' dredge choices.
Grammar diagnostics are distinct from paid-card behavior. Initial board and
mana setup does not establish natural-game or universal-layer coverage.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_conditional_player_draw.py
```

## References

- [Wizards release notes, page81](https://media.wizards.com/2021/downloads/TSR_Release_Notes/EN_MTGTSR_FAQ_20210118.pdf#page=81)
- [Official rules effective November6,2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020261106.txt)
