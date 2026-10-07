# Bounded Announced Target Shape Validation

Only targeting._target_reference_shape changes. Before accessing/iterating known
containers it requires a dictionary root, list target_card_ids, dictionary
 target_distribution/mode_targets, dictionary mode selections, and nonempty string
card-ID leaves. Distribution player keys retain the existing string1/string2 and
integer1/integer2 forms. Scalar target_card_id=None and valid empty containers keep
existing behavior. Unknown keys/mode metadata are not validated, and distribution
amount values are deliberately not interpreted here: existing legality owns them.

Shared capture and receipt validation use this helper. Malformed recognized shapes
raise existing ActionRejected('Malformed announced target references') rather than
TypeError/AttributeError. No engine/API catch, schema, amount/grammar expansion,
name exception, legacy absent-reference change, frame recapture or API-field addition.
Only this function's AST changes; all other2057 inherited source-file bytes and
all other targeting AST checked against frozen fShdn2 before graph refresh.

Immutable dependency: announced-target-object-reference-fix/mtg-target-object-reference-fShdn2
source-only.tar.gz SHA256556dae5f246ffae6ac1390545587f9344668d904cae77aa0911d981174c88a0b.
Original malformed40/HTTP12 test-only dependency XG7mjq tests-only.patch
SHA256ac98b119bb0d96f279224afed89195f438561f754cf2816349af8a54df99bacf.
Original audit test files remain byte identical. Production preimage targeting
c2461718a26abeb036bc5c99f9cefda420f90ddeb766e778b73c6451a7f23092;
postimage60029fa1e5d9630757eab83f23217b4f2ef3c6f6a850f707141334a064c4aa6c.

Historical pure40=10PASS30strictFAIL12.17s, HTTP12=12strictFAIL10.14s, allactual500
with root/controller/SQL equality and cold restores passed. Those archives untouched.
New pure seven whole modules166PASS2warnings49.91s, no error/skip/xfail, with ALL
SQLite and network denied. Original40 nowgreen; new54 structural/leaf/empty/player/
metadata/amount-noninterference controls, original12helpers, realpaidcopy10,
genuinegraveyard4, wholeFavorclause20 andFavorlifecycle26 allpass unchanged.
Pure identity objects exercise structure only, never fabricated gameplay cards;
amount-noninterference controls do NOT claim unsupported amounts are legal actions.
Actual paid canonical copy/graveyard/private Favor cases reuse existing fixtures.

HTTP12 NOT EXECUTED on this increment: waiting exclusive slot after parent/Erdos.
No HTTP422 closure claim from pure tests; final handoff must separately report its
actual terminal result. Scheduler2 preimage failures remain unadapted/immutable.
