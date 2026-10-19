# S1: native Ninjutsu entry transition

Scope: keyword_actions.resolve_ninjutsu only. Replace direct battlefield zone assignment with CardInstance.move_to_zone. Preserve source sequence guard, paid costs, timestamp/static-order assignment, tapped/attacking entry and event emission. No events/compiler changes.

Exact required keyword_actions preimage: 8c8e1b475fd762987fc21d869b5a38322c7ecc9d83271cf604efc2eb65d7d17a.
Final: 181527cd81419ecd56c9aa1c00333253e11ca88ac0bff535d9d46a07078a708f.
Dependency: frozen hand-entry audit source, which already contains the 2d000 source-incarnation fix. Product does not depend on consumer/API changes or an engine.py preimage.

Original twelve canonical audit assertions unchanged: baseline 4 failed/8 passed; after S1 2 failed/10 passed. Both source-sequence cases pass; both Cathars' Crusade cases remain ordinary failures, not xfails/skips. They are separate S2 matcher/instruction-routing defects. No full audit release-green claim.

Six new controls: baseline 4 failed/2 passed; after S1 all six pass. Valid entry invokes the shared zone transition exactly once; stale source never invokes it. Two genuine pending activations capture the same source reference: first enters; controlled return to hand changes identity; second does not follow it. Both seats, paid attackers/costs remain paid, snapshot restoration parity. Controlled departure explicitly clears combat membership and is not claimed as a causal HTTP bounce spell. That setup cleanup was added before the final after gate; the baseline fails earlier at the source-sequence assertion. No assertions weakened.

Combined audit gate: 16 passed/2 ordinary Crusade failures, 73 warnings, 24.02s, exit 1.
Serial regression/neighbor gate: 160 passed, 26 warnings, 63.60s, exit 0; exact module/node list and guarded invocation archived. Includes actual HTTP/restart source-identity tests, original two strict engine probes, whole opening-hand/counter/keyword/cycling/modifier/suppression neighbors. This is not a whole consumer gate.

Canonical full Ninja official intake, unchanged canonical observer rows and opening-hand fixtures inherited from the frozen audit. No fake cards/Oracle changes. SQLite only beneath own local root; network and outside-root SQLite forbidden by audit hook. Main/live/parent roots untouched.

S2 is separate preparation: modern controlled-entry predicates and bounded shared instruction delegation, not included in this patch. Unknown predicates/bodies must not grant partial rewards; paid choices/source context/targets must remain preserved. Parent coordinator confirmation is not human approval.
