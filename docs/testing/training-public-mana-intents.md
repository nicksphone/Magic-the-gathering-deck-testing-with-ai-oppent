# Public Mana Intent Compatibility

Separate increment over frozen selected-mana caller A8c5 plus the canonical
public-mana-choice-hints producer. Neither frozen caller nor staged 33685 changes.

Training accepts `required_choices` only as known presentation metadata. Actual
payment, hybrid and output selections still require complete Action parameters
and checked_action legality; metadata cannot supply omitted choices. Unknown
requested fields and unsupported output schemas remain rejected.

Canonical activation_costs/hybrid_symbols are reused rather than recomputed.
Missing fields retain the legacy producer fallback independently. Both-seat
Tower and Cairns tests cover actual whole legal-move intents, root immutability,
missing/unknown choices, equal observation/prompts, fallback and returned-data
alias isolation. Existing selected-mana privacy permutation checks remain active.

This is consumer compatibility, not GUI qualification or a full-hand performance
fix. No neural competence or expert-data claim is made.
