# Aura Departure LBF Preflight

Production scope: state_based_actions._apply_attachment_state_checks ONLY,
including its two local imports. Frozen original function SHA256
fe2cd885857b7b730297137a62c95c4ea6124849eab125bc9ebe467ee454bf3a,
whole-file preimage95b354eb8cdb1f29c5ab630a8352727673a57453a7167304f060ccb271e5f6b0.

Both illegal/no-target Aura branches now select the existing retained graveyard
plan and prepare its static cause while the Aura is still on the battlefield.
Only then emit real leaves_battlefield (capturing LKI), remove from the old list,
and call the SAME shared execute_graveyard_entry with prevalidated=True and the
prepared cause. Its existing move_to_zone/owner/destination/committed-entry logic
remains authoritative. No replacement priority, extra events, or creature-dies
receipt is invented. No zero-loyalty, lethal/legend, Bestow, equipment, or other
function is rewritten. The direct retained executor is necessary to avoid
reselecting eligibility after the requested LBF event; it is not a new routing API.

Original49 audit assertions are unchanged. New18 include six actual paid canonical
bounce/preflight-order cases and twelve explicitly controlled seam cases. The
controlled no-target/foreign-owner positions start from paid legal Pacifism then
assign only attachment absence/owner for a trusted seam: NOT actual detach or
control-changing spells. Four injected selection/cause failures prove preflight
precedes every event/list mutation for the tested single Aura. They do not claim
canonical naturally competing mixed-destination Aura support or add a choice API.

Actual cases cover both seats, GR/Rest in Peace EXILE, LBF/LKI, source identity,
false creature-death exclusions, paid Unsummon target return, cold HTTP/cache,
actor privacy, root/controller/SQL atomic rejection, independent snapshot-process
restoration. Whole-body artifacts are full canonical payloads from originalaudit;
no new Oracle fixture, name rule, or fakecard. No naturalgame/AI or wire-process
HTTP restart claim. Simultaneous multiple-invalid-Aura batch semantics are not
newly qualified; existing per-card iteration is retained unchanged.

Surgical incremental patch applies by function-anchored hunks; never overlay the
whole file. Parent/Jason's other three SBA functions are disjoint and require
parent composition qualification, not an assertion that their moving source was
run here. Exact gates/logs/dependencies/hashes are in the frozen REPORT.
