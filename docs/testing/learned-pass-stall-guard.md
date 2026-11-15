# Checked-Subset Learned Pass Guard

The learned router scores and validates every admitted candidate's Q/V output
and computes its existing checked unanswered terminal forecast before considering
the pass guard. A late invalid Q/V still rejects routing, including after an
earlier checked winning pass. Existing admission, feature/engine binding,
terminal ranking and unknown-blocker fallback remain unchanged.

If the highest-ranked action is a pass that is not a checked winning pass, the
router may reuse the agent's existing `_should_break_stall` and
`_best_proactive_non_pass` helpers. The latter receives only already admitted
non-pass candidates whose terminal prefix `(win is True, loss is not True)` is
not worse than the selected pass's prefix. This means not worse under the
existing checked unanswered terminal class, NOT safe against unknown replies or
all possible future play. The existing forecast limitations still apply.

The helper cannot introduce, materialize or retarget another action. It receives
deep-copied candidates; its result must have the exact canonical identity of an
eligible preadmitted candidate. The router returns a deep copy of that original
candidate. Unadmitted, changed or empty-attack results retain the selected pass,
not a blind `None` fallback into a different baseline shortlist. The existing
unplayable-X veto is retained. Resource-only `activate_mana_ability`,
`tap_nonland_for_mana`, `tap_land_for_mana` and `tap_lands_bulk` actions are never
offered as proactive progress by this guard.

The existing stall predicate retains legitimate early Control holds, opponent
turns and nonempty stacks. Forced passes or no eligible paid/meaningful option
retain the pass. Old protocol agent doubles without the required helper methods
retain their original ranking behavior. No broad exception handler is added.
The production change is solely within `choose_learned_action`; no card name,
card family, global helper, default policy, checkpoint or model is changed.

## Verification Scope

`tests/test_learned_pass_stall_guard.py` uses existing full-public-canonical
Factory fixtures and explicitly synthetic pass-preferring Q scores. It includes
both-seat modal damage and unrelated creature development, real Control/stack/
turn controls, terminal-prefix protocols, helper containment, late-invalid Q/V,
X/resource vetoes, root purity and private order/log invariance. The resource
control uses the actual offered Forest `activate_mana_ability`, not an inferred
old-style tapping hint.

Eight new checked full-turn cases start after an actual Spear cast, with either
pending or resolved priority passes and one paid burn spell. Synthetic Q prefers
passing in main phases; combat ties retain the real strategic shortlist order.
Own actions are genuine bound-agent choices and core-checked; only opposing
pass/empty-block continuation is conditional. These are finite canonical
regressions, not natural games, private trace replays or strength certification.

Raw Q can still prefer the wrong pass. The resulting policy remains the actual
tactical-safeguarded checked-subset hybrid, not pure learned competence or an
expert model. No fitted checkpoint is loaded, repinned or activated on the
changed engine. Test bindings are newly constructed numeric protocol fixtures,
not a conversion/adoption of the held candidate. Real-model qualification,
fresh-source training, rollout admission and any deployment remain parent-owned.
