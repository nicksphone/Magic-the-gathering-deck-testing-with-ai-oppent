# Activated-Sacrifice Zone Identity: Narrow Qualification

## Scope / Source

ONE production line in costs.py apply_activated_costs: card.zone=zone becomes
card.move_to_zone(zone). No check_cost_option_available/b919, engine, mana, AI,
training, API, importer, frontend, graph-main or live-source edits. Parent code
archive current-ai-mana-frontend-static-qualified-source.tar.gz SHA256
 a853b32bee1f50caa06e510da7a2af7410cd24077bc24799fcaded4f4cf8ab7b.
Source includes parent's perf+forwarding+cost witness+AI composition. Copy source
only, main external.venv; all test SQLite stayed local. Original875 files pinned;
874 other files remain byte-identical; entire costs diff is exactly one line.
Before costs86834afb19d4e5254a180043e0c3cd670818755036dc39ce3cac67107e0a4770.
After costs4ba22bbe98802ad0abd6af50efd09db8ab844a5e19631a9420dbce18d0bbc748.

## Semantics / Exile Difference

Existing leaves_battlefield events capture LKI BEFORE changing zone. move_to_zone
advances normal zone identity and clears departure metadata (suspend haste,
foretell, etc.). BF->GY deliberately does NOT immediately reset counters:
creature-dies collection can inspect them, then _finish_death_event resets them.
Read-only event observations verify +1/+1 counters2 available during creature_dies,
last-known counters/power/incarnation retained, runtime counters cleared afterward.

BF->EXILE clears runtime counters earlier, using normal zone-transition semantics,
before sacrifice event; no died payload is produced. Captured LKI remains2. Existing
post-event exile reset loop is retained unchanged, even though normal transition
already reset; the repeat is idempotent including real Skullbriar persistence.
No event ordering, replacement selection, owner destination, staging or LKI fields
rewritten. Exile reset timing is an intentional move-to-zone consistency change,
not a claim the raw runtime counter dictionary stays identical to old behavior.

No guessed sequence+1 test oracle: expected metadata comes from existing normal
move_to_zone on a clone. Actual checked activation remains root-pure; tests compare
zone identities/metadata, proper owner graveyard/exile, exact mana and actual LKI.
Both seats: Tower OTHER creature and Basal Thrull SELF sacrifice, foreign-owned
controlled victims/sources, Rest in Peace exile, normal GY, returned incarnation,
Chromatic Star actual death draw vs exile suppression, Hangarback observed deferred
counters/LKI, Skullbriar retained counters, actual Dream Devourer foretell then cast
then sacrifice, real Woe Strider-created Goat token sacrifice/cessation. Riftwing
Cloudskate test seeds legal post-suspend-cast haste metadata; it is NOT a fresh full
Suspend-UI protocol test. Existing lifecycle/API neighbors qualify their protocols.

## Canonical Inputs

Ten unchanged raw Scryfall records from existing Sept27 public Oracle bulk.
Compressed source SHA17cf0c4d0c96dde18337326626037732d0ff219c498d19ef0c9536f6db62dc13;
38690 records, bounded original scan2MiB/line1GiBtotal, no HTTP calls. New fixture
provenance pins record IDs/oracle IDs/canonical row hashes/fixture hash; existing
fixtures not edited. No names in production rule, fake aliases, rewritten Oracle,
custom mana balance or hidden AI decisions. Token is actually engine-generated
from printed Woe Strider, not a fabricated token card. Foretell control executes
real special action, resolves Dream's reward trigger, casts in later turn and
resolves actual Basal creature. No intentionally omitted pending stack step.

## Strict Before / After

Final SAME39 unmarked tests on unchanged source:36fail3pass1.86s,exit1.
On one-line fix:39pass1.56s,exit0. No xfail or deselection in identity module.
Earlier35-case baseline32fail3pass1.84s, corrected31-case28fail3pass1.67s retained.
Initial exploratory30fail1pass also contained unrelated Hangarback quantity mismatch
and foretell setup error (reward trigger still pending). Initial post-fix29pass2fail
were observer errors counting empty died batches as actual deaths. Observer now
filters actual victim IDs; no production change to suppress/relabel death events.
All initial logs retained, not retrospectively called semantic qualification.

22-module neighbor invocation:1032pass10skip2xfail94warnings76.35s,exit0.
Exact list neighbor.files. Source/test version35-case recorded in
neighbor-frozen-source.sha256 and test-at-neighbor-freeze.py before adding four
foreign-Basal variants. Ten skips are explicit real-loopback Suspend composition
opt-in tests requiring MTG_SUSPEND_COMPOSITION_HTTP=1, not ordinary failures. No
claim those10 executed. Other resource/joint/Suspend/foretell actual ASGI/reload
checks execute on local isolated SQLite with exact MTG_ISOLATED_TEST_ROOT.

Final13-module vector/resource invocation:656pass2existing Song type-layerxfail,
16.97s,exit0. Exact list vector.files; includes final39 identity cases, mandatory
base/mixed vectors, additions/produced types, snow/restrictions, nested life,
resource source reservations and variable grammar. Do not sum overlapping suites.
No broad matrix, historical fullhand diagnosis or future escape qualification.
AST-only own graph update exit0; original source and all frozen older artifacts
unchanged. Source fixture/test/new docs snapshots and exceptions retained private.

## Separate Consequential Remaining Gap

Canonical Hangarback Walker with2 counters, Tower sacrifice: LKI/deferred death
counters2 are correct, but printed for-each-counter Thopter quantity resolvesONE
instead ofTWO, both seats. Separate test_activated_sacrifice_identity_limits.py
strict marked cases; --runxfail produces2fail1.13s. Neighbor2xf are these, not fixed
identity expectations. No Oracle inference/effect parser edit authorized or made.
It is NOT caused/fixed by this zone transition change; initial baseline already
reproduced it. Generic counter-dependent death token multiplier is next related
family investigation, not a named-card patch. Phase-aware automatic escape also
still requires its separately reviewed shared witness/parent engine contract.

Original immutable phase-aware counter xfail markers would now XPASS if composed;
parent acceptance may unmark them separately, never modify archived originals.
New39 ordinary tests already provide strict acceptance without guessing counters.

## Integration

Apply costs-only.patch AFTER parent's current composition, independent of old
proposal/source fixture artifacts. Clean git apply--check on exact unpatched base
recorded. integration.patch combines ONLY that line +two NEW test modules +new
canonical fixture/provenance +this NEW doc. No other existing file changed.
Requalify parent's later type-layer/caller/AI deltas separately. Larger witness
materialization/source staging/public future-choice design remains proposal-only.
