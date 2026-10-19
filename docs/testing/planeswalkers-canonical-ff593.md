# Planeswalker Canonical Fixture Migration

Current result: all 73 cases pass after the separately authorized printed-index
adaptation. They also pass unchanged in the later whole
[406-case mixed component](canonical-timing-planes-combat406.md). Earlier held
epochs below are historical evidence, not the current component status.

Base is immutable ff593d5171fb2f427970f123fe68cf1798e25b1c, never a moving
parent checkout. Only test_planeswalkers.py and four NEW test/data/doc paths
change. No production/shared helper/AI/schema/App/API change.

## Canonical facts and retained intent

Complete Island (60 fields, seed row50) and Teferi, Time Raveler (63 fields,
row146) are reused from the existing pinned complete official seed155 and
provenance, without requests or abbreviated Oracle. SOURCES binds file/row/
object identities. A truthy explicit display-only image prevents placeholder
I/O. Full normalized parent data enters the actual MatchFactory before stock
capture; only runtime identity/controller/zone/instance_order are adapted.

All five original Factory calls keep their exact two60-card quantities,
unspecified seed, actions, X materialization, controller/priority/resource
poses and native captures. Teferi is born with printed loyalty4, then retains
the ORIGINAL runtime loyalty2 assignment. All five old names and12 assertion
ASTs are exact. Complete function/whole-byte inverses permit only five deck
RHS replacements, one Teferi birth span, and the added local helper import.
No printed baseline is retagged, cleared or reinitialized after birth.

Test Walker, X Walker, Red Trampler, Protected Walker, unnamed combat bodies
and removed-target role mutations remain explicit original protocol vectors.
Their literal bodies remain unchanged; this does NOT declare them canonical,
waive literal Task1.3 scope, or claim all module vectors are real stock cards.

## Actual TDD and strict remaining failure

The SAME two WHOLE modules collect43 cases: all five old +38 NEW.
- Before original fixture migration:36 FAIL /7 PASS, pytest5.051s.
- Canonical candidate:42 PASS /1 FAIL, pytest6.729s; outer exit1.
- All38 NEW fidelity cases pass; no skip/xfail/deselection/old assertion edit.

NEW tests observe original actual Factory inputs/births and the first attack
consumer, not just a standalone helper. Independent pinned-source typed
expectations separate physical loyalty4/current loyalty2, missing printed
stats, complete text/type/cost/colors, and retained records. Coherent current/
retained and physical-field corruption controls reject; objects are fresh.

The remaining ORIGINAL failure is
`test_trample_excess_damage_to_protected_planeswalker_is_prevented`:
expected loyalty5, actual2. It starts from canonical Island colorlessness
`colors=[]`, then changes the attacker name/cost to its existing synthetic
Red Trampler role without changing colors. Former incomplete Island had
`colors=None`; `_printed_color_symbols` then inferred red from `{3}{R}`.
With explicit `[]`, it correctly does not infer red from cost. The unchanged
protection path therefore does not prevent that3 trample damage. Source trace:
`combat._deal_unblocked_damage` -> `_damage_prevented_by_protection` ->
`protection.protection_match_reason` -> `colors.card_color_names` ->
`card_color_symbols` -> `_printed_color_symbols`.

This is a demonstrated fixture-precondition incompatibility after complete
Island facts, NOT a demonstrated canonical protection engine bug. No claim
that all canonical engine rules are qualified. No resource/pose/assertion or
product correction is made to conceal the failure. A separate parent decision
is required before any adjustment to that original synthetic role.

## Enforcement and scope

Existing qualified pure runner is reused with ONLY ceiling150->100. Both
stages have bound900TERM/+15KILL, --noconftest, all SQL aliases/socket/process/
provider/main denied before project imports (nine real denial controls), no
unexpected I/O, full source/FRESH equality, FD equality, no child/new thread/DB.
Retained runtime is3674 regular files/four links/429 directories. Logs and
JUnit preserve both epochs. No SQL/browser/native/HTTP/CI/game/performance
qualification, and no Task1.3/Phase1 completion is claimed. This doc is postgate.

## Separately Authorized Explicit Protocol Color Correction: 46 PASS

The prior43-case HOLD42P1F and first36F7P archives remain immutable. A NEW
isolated followup adds ONLY `state.cards[atk].colors = ["R"]` next to the
existing Red Trampler mana-cost pose. This is explicitly synthetic mechanism
setup, not a change to Island RAW/materialization/printed capture, not a real
red card, and not a literal Task1.3 waiver. No expectation is relaxed.

Three NEW strict controls preserve canonical Island colorlessness for both
seats and capture the actual original Red Trampler fixture at the combat
consumer. They verify explicit live red, untouched colorless retained physical/
copiable stock, native red-color/protection predicates, actual combat loyalty5
and player life20, plus unchanged complete Island RAW and helper projection.

With identical NEW controls, before that one-line correction the SAME two whole
modules give44 PASS /2 FAIL; after correction they give46 PASS /0FES in6.763s
(pytest),8.345s driver. Both failures were the original protection assertion
and the new explicit-red assertion. All old43 identities remain first, all five
original test names/12 assertion ASTs/actions/resources/X/control poses are
retained, and all previous38 fidelity cases pass. There are no filters/skips/
xfails. The qualified100/900TERM/+15 pure guard body is unchanged.

Both new stages retain all nine real preimport denials, full source/FRESH
hash/link/directory equality, FD equality, no unexpected I/O, database, child
or new thread. No SQL/HTTP/browser/native/AI/product/CI execution is qualified.
The separate future two-HTTP-role profile proposal requires exact parent-
supplied node/body bindings and independent review; it is NOT implemented or
activated by this component. Parent owns integration and future mixed gates.

## Separate Positive-Loyalty Canonical Stage: 72 PASS / 1 INDEX HOLD

The prior46-pass component and its older43-case HOLD are immutable. This NEW
stage removes the handwritten positive Test Walker/X Walker Oracle assignments
from the original module, replacing those two constructor spans with complete
Teferi, Time Raveler and Ugin, the Spirit Dragon Factory births. The original
current loyalty3/4 assignments remain. Teferi's printed starting loyalty4 and
Ugin's7 remain in their physical/copiable records; no reseal, retag, false-fact
flag, guessed printed data or global alias is used. All original resources,
actions, native captures, AI difficulty/materialization and12 assertion ASTs
are unchanged. Remaining combat protocol vectors are not a literal-scope waiver.

Both parents already exist in the complete pinned official seed155. Ugin is
full66-field row110, SHA256
a7eaf555f3ec52827474274c5bf4eceadcc5afa29988b82530f35cd9b546062f.
No intake/network/SQL request is needed. Only its local source-index entry and
the corresponding helper index hash are added; helper function bodies do not
change. All raw text/printed order and source-name binding are retained.

Three WHOLE modules collect73 cases, preserving the prior46 identity prefix
and adding27 NEW first-consumer/birth/order/corruption/native-action cases.
Actual baseline against the still-toy positive setups:48 PASS /25 FAIL.
Actual full canonical replacement with all old assertions retained:72 PASS /
1 FAIL in9.651s pytest (11.233s driver), outer1. All27 NEW cases PASS. The sole
failure is the old `abilities[0]["x_cost"] is True` assertion.

Independent full RAW proves Ugin's actual printed costs are +2, -X, -10, so
its X index is1, not0. NEW tests compare ALL printed/native cost and body order,
confirm index0 is not X/index1 is X, obtain that genuine index1 offer from
RulesEngine, materialize it using the original master/Control policy, and
actually execute it: loyalty4 decreases by chosen positive X, activation is
recorded once, and the real engine StackItem retains the actual source/controller.
The original two-offer contract also passes with full Teferi +1/-3 text.

A separate PROPOSED_INDEX_ONLY.patch records the faithful single operand0->1
adaptation for parent review. It is NOT applied or executed. Native order and
all other assertions/actions/resources are unchanged. No engine/AI policy fix
is indicated by this stale index failure; no whole-green qualification is
claimed until the explicit parent-authorized index adaptation is tested.

Same qualified100/900TERM/+15 pure runner, three declared whole modules, no
filters/skips/xfails. Both new stages have nine real preimport denials, no
unexpected I/O, full source/FRESH equality, FD equality, no child/new thread/DB.
No native/HTTP/SQL/browser/current whole-backend/Phase1 completion is claimed.

## Parent-Authorized Printed X Index Adaptation: 73 PASS

After the RAW/native proof above, parent explicitly authorized ONLY the old
positive assertion index0->1 for Ugin's printed +2,-X,-10 order. A NEW isolated
source uses immutable a32dbd0d67586d5f6e4d5dcea2ec8860ff9ee550, the six frozen
canonical fixture postimages, and that exact one-operand patch. All five original
functions, other11 assertion ASTs, actions/resources/current-loyalty4 pose,
starting-loyalty7 physical record, and all27 NEW index/materialize/pay/stack
controls remain unchanged. No engine reorder/hardcode or source-fact adaptation.

ONE unchanged pure WHOLE three-module run gives73 PASS/0FES,9.510s pytest,
11.126s driver, outer0. All73 ordered identities match the prior72P1F stage;
all219 phases pass. The previously blocked original X test now reaches all of
its materialization/payment assertions. No extra46/44 cohort or RED rerun.

Nine preimport denial controls remain effective with no unexpected I/O, full
source/FRESH equality, FD equality, no database, child or new thread. Ceiling100,
900TERM/+15 bounds, no filtering/skips/xfails, no permission changes. a32 versus
ff593 has no backend production change; its unrelated published fixture/docs/
graph delta is retained as immutable input. Parent owns later coupling and
publication. All43/46/73 earlier epoch roots/archives remain immutable.

Final recipe: apply PUBLIC_COMPLETE.patch ONCE to exact a32 preimages. The
separate ADAPTATION_ONLY.patch is the authorized one-operand historical delta;
do NOT apply it again after the cumulative patch. No SQL/HTTP/browser/native,
whole-backend or literal Task1.3/Phase1 completion claim follows from this pure
fixture component. Remaining protocol facts are not a scope waiver.
