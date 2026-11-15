# Automatic Mana Material Preservation

Automatic paid-mana optimization must not discard a hand card or sacrifice an
extra permanent merely to preserve an untapped ordinary mana source. Compare
actual planned outcomes by remaining non-token cards in the payer's hand and
battlefield, then remaining tokens, then the existing mana-flexibility/life score.
The announced spell's reserved additional costs are unchanged.

This is a conservative automatic-payment preference, not a prohibition on paid
mana abilities. Necessary discard/sacrifice funding and explicitly selected mana
activations remain supported. It does not value individual cards, certify an
optimal payment in every position, or change the separate free-only search.

Canonical Skirge Familiar and Phyrexian Tower regressions cover both players,
Deadly Dispute and Village Rites, ordinary-land alternatives, necessary paid
funding, explicit activations, unchanged inputs, and snapshot/replay equality.
Tower's ordinary colorless tap remains a valid free source.

The corrected pre-fix regression suite had six material-preservation failures
and fourteen passing controls. After the fix, eleven whole neighboring modules
passed all 287 cases. Early new-test mistakes are retained in private evidence,
not treated as product failures. New training traces must identify this engine
change; older unnecessary-discard outcomes are not optimal-action labels.
