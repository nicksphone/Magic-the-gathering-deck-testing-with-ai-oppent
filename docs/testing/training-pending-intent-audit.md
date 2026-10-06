# Pending Choice Intent Audit

NEW tests/report only, pinned source-only main commit
`3ccbdf203a4ee1aeb848e219769c9dfac0f20e8c`. No production or main changes.
The main graph was read first; its report names built commit d88dbf04, so that
map is stale relative to the pinned source and is not qualification provenance.

## Bounded Evidence

32-case serial local-SQLite gate: 16 FAIL / 16 PASS, 91 warnings, 36.34 seconds,
exit 1. No skips, xfails, deselection, production substitution or contradictory
unsupported-acceptance witness. All 16 failures are DID NOT RAISE at the sole
lookup_intent rejection expectation. Strict lookup rejects; actual HTTP returns
422 with full match/controller/SQLite dump unchanged. The finally assertion
also confirms the training root is unchanged after the failed expectation.

Two actual canonical families, both seats:

- choose_mechanic: Daretti, Scrap Savant's +2 yields a private bounded discard
  prompt. Explicit zero-card and one-Opt choices draw exactly zero/one, preserve
  the independently unselected Savannah Lions, and leave loyalty at five.
- choose_optional_effect: Reclamation Sage has already selected the visible
  opposing Sol Ring as its trigger target. Explicit accept destroys it; decline
  preserves it. Missing/stale stack/invalid boolean choices reject.

Unsupported requested aliases are selected_card_ids (instead of mechanic
card_ids), choice_id='decline' (instead of optional accept), and unknown_choice;
nonnull/null forms are all tested. These are outside the corresponding public
schemas. In particular choice_id is a real MechanicChoice field, but NOT an
OptionalEffectChoice field; the audit does not misclassify recognized nulls.

Sixteen independent positive controls cover actual training and HTTP whole legal
views, strict raw action equality, exact encoded-action replay, pending snapshot
restore, checked HTTP execution and DB restart, recognized malformed requests,
wrong-seat rejection and actor-private observations. Opposing hidden hand/library
identity and order permutations leave observation/prompt input bytes unchanged.
The other seat gets no pending prompts or API legal moves; actor-only discard
cards stay absent from its known-card memory. Unsupported requests are never
executed in order to establish a positive control.

The read-only normalization probe independently records all 16 raw-reject /
intent-drop cases with caller request and full root unchanged. It observes that
the normalized result equals the independently declared valid action; this is
diagnostic evidence, not an unsupported-acceptance test requirement.

## Narrow Proposal, Not Implementation

Extend only lookup_intent's explicit public-model guard to MechanicChoice and
OptionalEffectChoice. Reject unsupported aliases/keys, including null, BEFORE
complete_action filters them. Preserve all actual chosen card_ids/choice_id/
damage_assignment/stack_id/accept parameters and continue using checked_action;
never infer choices from offered options or suggested selections.

Qualified Daretti training presentation keys are kind, options, count,
min_count, label, option_labels and option_type_lines. The optional view contains
only its three proper schema fields (type, stack_id, accept).

There is an explicit compatibility decision before implementing that proposal:
the raw mechanic API/engine whole view additionally contains effect_controller,
followup_effect, player_id and resolving_item, which sanitized training hints
and observations exclude. The current positive tests faithfully capture raw
whole-view acceptance too. Do not blanket-treat client-supplied continuation or
resolving state as presentation/authoritative choices. Preserving those controls
would require validating present server-owned context against the current pending
decision, or an explicitly approved safe caller projection/test contract. No
such production change or choice has been made by this audit.

## Limitations

This stops at clear two-family evidence. The actual ordering schema name is
choose_trigger_order, NOT reorder_triggers; that family is not audited here.
No claim covers other mechanic kinds, trigger-target/order/replacement encodings,
dataset action-alias completeness, browser behavior, neural competence or expert
data. Original guard/audit archives remain immutable; no completed prior gates
were restarted. All databases used for this audit are disposable and local.
