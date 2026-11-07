# Bounded Combat Projections

The AI previously enumerated up to 4096 block-search nodes, then resolved every
retained assignment using full native combat. Four attackers and five ordinary
blockers can produce 3125 assignments within that enumeration limit. A limit on
enumeration therefore did not bound the expensive native projection stage.

## Policy

- Keep complete legal-intent enumeration and its existing unknown-on-exhaustion
  behavior. This changes AI search, not legal combat declarations.
- Keep every intent in the candidate set when there are at most 64; the existing
  conditional-search filters still apply. Larger sets use a deterministic
  16-intent shortlist drawn from survival, trade, and material-retention estimates.
  Reserve legal no-block as a candidate. Unknown public stats remain unknown.
- Use estimates only to select candidates. Actual combat, triggered effects,
  payments and final board scoring still run through the native engine.
- Exact defensive-response callers explicitly require complete coverage. More
  than 64 intents, or any unresolved admitted defense, yields unknown instead of
  a winning certificate. Approximate strategic forecasts remain conditional.

The shortlist is not guaranteed optimal. Its size is also not a whole-decision
time limit: small sets can use 64 simulations, and the existing unblocked probe
and next-combat lookahead add work. No-block and keyword/retention tests must
remain in regression coverage rather than assuming a lower count proves quality.

## Measurement

On one retained native decision, the earlier baseline and enumeration-cache-only
version each reached a 150-second cooperative limit without returning an action.
The candidate cohort completed the same input decision in 10.63 seconds; its
returned action was independently accepted on a detached native state. Input,
agent, legal moves, class priors and random state were unchanged.

That candidate cohort also includes the separately tested hybrid-payment,
explicit Aura-choice, and static-tax query improvements. This is not a pure
single-change speed ratio, final-action equivalence against the censored runs,
whole-game result, learned-model result, or a claim of UI-ready latency.
Private replay artifacts are intentionally not published in this repository.
