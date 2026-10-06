# Activated Subtype Sacrifice Costs

The activated-cost parser now reuses the existing fixed-cost component parser
for complete creature-subtype sacrifice clauses. The shared subtype registry and
existing eligible-resource/payment operations are reused, without card-name
dispatch or Oracle edits. Exact clauses such as sacrificing a Goblin or two
Goblins preserve their subtype and quantity instead of becoming arbitrary
creature sacrifices. Unsupported qualifications and mixed subtype/generic
constraints stay unsupported rather than flattening into a different cost.

Canonical unchanged Skirk Prospector, Goblin Instigator and Llanowar Elves
fixtures test the actual selected-payment helpers in both seats: self versus
other Goblin, wrong subtype/controller, reserved resources, missing/duplicate
selections and whole-root rejection preservation. Grammar-only examples are
parser tests, not fabricated card fixtures. They do not certify an arbitrary
Oracle clause or effective subtype-changing effects.

This is a **cost-layer prerequisite**, not complete immediate mana activation.
The public mana action/executor still needs coordinated selected-resource
forwarding and sacrifice-only admission; current source-only/tap-only admission
does not recognize Prospector's ability. Automatic mana planning, human controls,
training choices and hybrid mixed-output selection require their own composed
acceptance. No live database, game or canonical card data is modified by tests.

## Executed Qualification

Against tracked `e4d8aa8`, the new suite reproduces seven failures and fourteen
passes before the parser change. After the change, nine composed suites pass
418 tests in 106.61 seconds (73 pre-existing datetime deprecation warnings):
activated subtype sacrifice, activation payment choices, joint activation
payment, mana abilities/system/self-sacrifice, additional and qualified spell
costs, and training mana choice coverage. One initial command used a nonexistent
test filename and collected no tests; its failed command log is retained, not
counted as acceptance. No full browser, real Prospector immediate-activation,
hybrid-vector or expert-play claim follows from this helper-level gate.
