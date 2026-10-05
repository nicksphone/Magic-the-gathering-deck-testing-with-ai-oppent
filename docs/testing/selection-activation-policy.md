# Paid Selection Activation Policy

Initial sidecar base: isolated e645456 plus the frozen selection projection.
The parent has now wired the consumer into production source; see the
[integration scope and evidence](selection-policy-integration.md). No rules
handlers or live database contents are changed by this policy.

## Integrated Consumer Sites

Four consumer sites use the helper. When inventory is unavailable, ranking keeps
its legacy fallback without overriding known interaction reservation; unknown
does not become a zero-hit probability or a fabricated acquisition.

1. `_rank_moves_query`, activate_ability: if `selection_activation_plan` returns
   a plan, replace the existing flat +2.5/+4 selection bonuses with
   `selection_activation_score(plan, hand_value=1.25, interaction_reservation=6)`.
   Keep unrelated activation/payment/tax branches unchanged. The constants here
   reuse existing board+strategic hand value and instant reservation, not new
   card-specific weights. Do not apply the flat text selection bonus again.
   A reconciled zero-hit inventory is ranked at negative infinity, not treated
   as unavailable prior. Without this domination guard, a negative pass/closure
   bias can still put a pure zero-hit inspection above passing. It does not
   restrict engine legality or reject an unknown prior as known-ineligible.
2. `_uncached_strategic_position_score`: only when `settled_public_position`
   returns None, add `pending_selection_expectation(state, player_id)*1.25`
   (None means unsupported/no feature). Actual cost is already in the board.
   Never insert hypothetical cards or turn this expectation into legal actions.
3. `_strategic_line_score`: add the reservation from a supported selection plan
   at the same point as `_instant_value_reservation`, using the existing6 value
   when it loses all previously payable known interaction. Existing line search
   blends apply unchanged; do not count acquisition expectation here again.
4. `_best_proactive_non_pass`: exclude a supported known-prior selection plan whose
   `selection_activation_score(...same weights...) <= 0` from forced
   anti-stall conversion. Otherwise Strong can bypass ranking and force a
   zero-hit activation or consume reserved interaction anyway. Unknown-prior
   plans retain the existing fallback unless they lose known interaction. This guard is
   not a restriction on engine legality, ordinary ranking, or emergency digs.

The value1.25 is valid for this pinned consumer only: .9 board hand count plus
.35 strategic hand count. If consumer weights change, pass those weights rather
than treating them as mechanic facts. Helper exports probabilities/facts; policy
utility weights belong to the consumer. No unconditional activation mandate.

## Semantics Boundary

Admit complete engine-backed optional creature/mana-value selection clauses,
not card names or partial label keywords. Use submitted own-list inventory minus
known own cards; opaque library identities/order and opponent hand are never read.
At most one acquisition is possible; fractional probability is not a guaranteed
hand card, executable card, conditioned top order, or selection-quality estimate.
Absent/inconsistent own inventory or known-library inspection invalidates the
exchangeable prior. Existing projected state stays conservative for filtered
choices. Unsupported rules remain unsupported; this helper does not add handlers.

## Qualification And Limits

Recruitment Officer's canonical complete optional creature/mana-value clause is
admitted. Duskwatch Recruiter's unbounded creature clause and transformed
Azcanta's noncreature/nonland clause infer `noop` on this base; tests assert that
they expose no selection activation. Their unmodified named-card JSON responses
and provenance hashes are preserved as unsupported witnesses, not new handlers.

Actual production-agent tests cover both seats, Tempo/Tribal/Midrange/Control, Master and
Strong, six scenarios: empty-hand favorable selection, reconciled zero eligible
inventory, insufficient mana, deployable Serra Angel, lost payable Counterspell
representation, and an actual lethal Lightning Bolt with Counterspell available.
They check legal actions, hidden library-order/opponent-hand metadata invariance,
full root bytes including RNG, and restored-snapshot decisions. These are seeded
fixture positions with canonical existing cards, not natural game observations,
legal competitive deck recommendations, learned-quality labels, or win-rate data.

Own-list forecast uses an exchangeable inventory prior, not top identities or a
best-of-four card-quality score. Known library inspection, unknown removals,
unreconciled inventory or unsupported multiface inventory return unknown prior.
Pending feature admits only a single matching own activation without additional
stack items, copied data, or unsupported choice continuations. Existing actual
selection resolution remains authoritative, including zero-hit private inspection.

Reservation reports loss of all previously mana-payable known instant interaction;
it does not certify future legal targets or opponent responses. Its6-unit policy
price follows the pinned consumer's existing instant reservation, is waived at
end-step/cleanup, and should be reviewed by the parent when integrating. Generic
ability-cost/public prohibition checks are still the actual engine's responsibility.
