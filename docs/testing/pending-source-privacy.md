# Retained Source Privacy

Production ownership is exactly decision_view in backend/ai/information.py and
public_card_ids in backend/game_state/observations.py. Retained public frames
do not reveal a physical source's new hidden incarnation. Actual STACK cards,
including popped paused-resolution sources, remain public. BF/GY/face-up exile,
owned hand, explicit inspection and durable public-return memory are preserved.

The NEW f583 tests are additive only:

- test_pending_source_privacy_goldens.py: two genuine paid Channel/Zombify/
  Unsummon episodes, public HAND/new-sequence records, canonical identity,
  restored memory, retained Channel frame/ref and private permutations.
  Metadata mutation is an internal information-flow probe, not a lawful print
  change or a genuine library-trip episode. Existing canonical Humility fixture
  suppresses ETB; this f583-only golden does not claim an old ETB is pending.
- test_pending_stack_privacy_goldens.py: four paid Index/Ponder episodes retain
  popped physical STACK visibility and owner-only explicit library inspection.
- pending_source_privacy_support.py contains the twelve AST-exact canonical
  helper functions from the historical audit, without importing its test suite.
  The hand-source-causal/raw fixture bytes are unchanged. These dependencies are
  NEW to f583 and must not overwrite an existing destination file.

The unchanged full historical35 audit was run separately on f583: 17 PASS and
18 FAIL (later battlefield LKI attached to an old hand-origin frame). Its complete
source, assertions and failure ledger are preserved in the v1 packet. This is
an independently missing HAND-source product composition, not a privacy-test
failure, and not silently certified or discarded by this minimal packet.
All six NEW goldens,25 memory and60 library-reorder tests passed in that run;
the v2 helper namespace receives its own follow-up qualification.

No compiler changes are required by this additive f583 packet. The older
component's strict Channel+ETB 667 tests remain separately archived and passed;
that compiler-dependent NEW24 is not installed by this privacy-only packet.

Existing results: product-fixed667 PASS with raw wrapper0 and closure PASS;
isolated2331 neighbors950 PASS with pytest0/output0. Their raw source compare1
is preserved: six declared SVG additions, zero changed or removed original
inputs. Raw wrapper96 is preserved; independent post-terminal closure PASS is
a separate observation, not a wrapper relabel. All are pre-maintenance results.

Pip-only offline maintenance is documented separately in parent-integration/
pip-only-maintenance-20261007: pip26.2.1, pipcheck0, identical nonpip bytes and
versions. New runs must cite that provenance; old ledgers are never rewritten.

Complete canonical Brainstorm/private hand-to-library support is missing in
this baseline. No fabricated private transition, partial draw-only response or
counterfactual metadata mutation is counted as causal Brainstorm coverage.
Implementing a complete response remains a separate upstream product scope.
