# Closed-board Escape Fuel Check

Mana payment stops before permutation search only when a native escape
postcondition needs more eligible graveyard cards and a closed board proves
that paying mana cannot supply them. Tokens do not supply departed graveyard
fuel. Unknown text, retained effects, linked exile contexts, counters and
potentially fuel-producing discard or sacrifice costs retain the old search.

The check does not lower the search budget, change escape costs, infer a
payment choice or score an AI action. Custom payment predicates are unchanged.

Regression coverage includes both seats, pending resources, root/RNG purity,
and native escape funded by Skirge Familiar, Phyrexian Tower and Blood Pet.
The two focused modules contain 34 cases. The selected 13-module regression
cohort contains 321 cases; it is not a full backend or playing-strength gate.
