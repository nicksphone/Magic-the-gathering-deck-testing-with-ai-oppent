# Self-Entry Public Return Witness

This TEST-only repair was measured on immutable source `f1fdfd0e0b3e5d953e51cd5a73240aebbc2fa214`. It changes one witness expression, not the production observation, serializer, rules, knowledge, stock-capture, or privacy implementation.

The unchanged whole module had 20 PASS and 4 FAIL (19.98 seconds). Both seats' source-bounce and target-bounce cases failed before the HAND assertion: raw witness records included empty `knowledge_snapshot: {}`, while the canonical serializer intentionally omitted that empty optional dictionary. Every observed returned record was already HAND with sequence delta zero. The original HAND, public reference, full Oracle, payment, copy-purity, and private-information assertions remain unchanged.

The witness now captures the complete canonical serialized `card_observations` record before JSON restoration. Serialized viewer keys are looked up as strings; witness viewer keys remain integers. No field is manually dropped, and no record or captured fact is rewritten.

Nine new serializer-wire PROTO controls distinguish native empty dictionaries from other empty values and dictionary subclasses, retain all nonempty fields, check deep-copy isolation, and verify root purity. Their opaque nonempty metadata is not an eligible knowledge profile, game Oracle, completeness proof, or engine-admission control. They reproduced two failures on the old expression (7 PASS/2 FAIL), then the actual whole original24 plus new9 passed: 33 PASS, zero failures/errors/skips/xfails, two warnings, 18.71 seconds. All 71 original assertion ASTs and source segments are preserved.

Global SQL, socket, process, and provider denial preceded collection. Eight finite native/constructor pre-denials were observed; there was no positive SQL, network, or child role. Original source files and all 3678 runtime entries remained byte-equal during each run, with no unexpected I/O. Closed own-path fuser checks returned exit1 with no owner output. An earlier collection-only harness path-prefix stop executed zero test bodies and remains separately preserved.

This closes the scoped witness regression only, not whole CI, natural-game quality, measured AI strength, or a broader transition/knowledge certificate. No mixed-SQL neighbor run was needed because the changed expression is private to this test module. Graph metadata updating occurs after the measured run and is not retroactively included in its before/end byte-equality claim.
