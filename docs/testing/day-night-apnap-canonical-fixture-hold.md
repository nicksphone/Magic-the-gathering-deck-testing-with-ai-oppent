# Day/Night APNAP Canonical Fixture Candidate

Fixture-only candidate on immutable6900e9d1dd0bf5589a0c32b6c12cd05effc02e87.
Status: HOLD, not a green qualification or a production/rules change.

The original six test names and all29 assertion ASTs remain unchanged.
Only the simultaneous APNAP test's three named fixture constructors change.
IDs, owners, battlefield placement and transition/event sequencing are retained.
The helper emits no cast, entry or transform event while constructing facts.

Brutal Cathar/Moonrage Brute uses the complete already-pinned official parent
from seed155. Complete unmodified official HTTPS responses for Phyrexian Arena
and Corruption of Towashi, their hashes/identities and provenance are committed
under tests/fixtures/day_night_apnap_canonical. Production normalization and
physical-front projection are reused; the explicit image operand is display
only and prevents placeholder generation. No Oracle paragraph or face is cut.

New fidelity tests inspect the actual original test objects before
_untap_then_upkeep, covering both owners, both Cathar copies, complete supported
root/face projections, RAW pins/provenance, freshness and truncation negatives.
This is fixture-fact fidelity, not a stock-capture or complete gameplay proof.
The existing synthetic Daybound Werewolf, Night Watch and Free Draw specimens
are untouched and are not certified as canonical named-card positives.

The exact same five whole modules collected46 ordinary cases in both runs:
test_day_night, test_day_night_apnap_fidelity, test_day_night_turn_boundary,
test_transform_draw and test_transform_triggers. Original RED:41PASS/5fidelity
FAIL in4.90s. Canonical candidate:45PASS/1original APNAP FAIL in5.30s; all9new
fidelity cases pass. No errors, skips, filters or xfails.

The unchanged APNAP test passes its four-transform assertions, then fails
because pending_trigger_order is None. Current complete Towashi text says
"a permanent you control enters transformed"; the existing production regex
recognizes only the older battlefield/under-your-control wording. Expected
groups[3,2], four transform triggers and five stack items are not weakened.
Production compatibility is a separately owned task; none is included here.

Both real gates preserve source2015 files and runtime4160 files/7links, exact
nine expected precollection SQL/socket/child/provider denials, FDs equal,
threads0, SQL0, children0, physical-native-games0 and no lease. An earlier
zero-collected harness TMPDIR write denial is preserved separately; only owned
scratch location was corrected, with no filesystem permission broadening.
The doc was written after the gates. No full Phase1/CI/release claim follows.
