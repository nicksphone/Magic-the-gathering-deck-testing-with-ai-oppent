# Recurring payoffs and safe mass destruction

Date: 2026-09-30 UTC.

## Implemented scope

One Oracle-grounded helper values supported recurring drain, draw and token
rewards for creature board scoring, cast ranking, threat assessment and
sacrifice retention. It reads reward text after the trigger condition, not
spent entry abilities. Existing sacrifice weights are retained rather than
retuned at the same time. Announced cast faces supply the evaluated surface.

For death rewards, actual engine event matching checks eligible public
creatures. A pure replacement query suppresses rewards when the death would
be replaced. Valuation never applies a replacement or changes diagnostic logs.
This estimates opportunities, not a complete sequence of future deaths.

The AI also projects fixed-cost mass-destruction casts when an opposing public
permanent has a printed numeric death/life-loss clause. A confirmed unanswered
loss removes that candidate from AI ranking, not engine legality. Hidden-zone
changes and unresolved trigger, target or replacement choices remain unknown;
unknown candidates are retained. Existing winning self-removal checks run
first, so a known winning line is not removed by the safeguard.

## Canonical fixtures

`backend/tests/fixtures/recurring_engines.json` retains fourteen real cached
Scryfall rows with Oracle IDs and source provenance. Tests construct specific
public board states, not competitive decks. No built-in list or printed card
definition was changed.

- Blood Artist versus Grizzly Bears: useful recurring rewards affect board,
  threat and cast values; Rest in Peace suppresses supported death rewards.
- Grim Haruspex requires another eligible nontoken creature; Torrential
  Gearhulk's spent entry ability does not receive a recurring bonus.
- Sheoldred's draw condition does not become an additional draw reward.
- At one life, casting Damnation into opposing Meathook Massacre plus Grizzly
  Bears actually loses under engine resolution. Across eight archetypes,
  Master chooses Naturalize on the payoff first, then resolves the wipe safely.
- Snapshot restoration preserves the decision; complete snapshots remain
  unchanged by valuation and projection. Opposing Blood Artist choices do not
  certify loss. Multiple replacement sources do not mutate valuation logs.

## Validation

Focused suite: 67 passed, including existing self-removal and projection-scope
regressions. Full backend suite in a tracked-source copy with these changes:
1,811 passed, 292 existing deprecation warnings, 282.40 seconds. This avoids
writing the live database. Frontend lint, build and unit boundary tests pass.

The full Chromium rerun passed action/choice, simulator, recovery, sideboard,
and natural AI, human-vs-AI and human-vs-human BO3 flows. The initial run timed
out waiting for sideboard application while a match operation was pending;
the rerun passed unchanged. That intermittent timeout remains unverified,
not a claimed fix. The separate earlier diagnostic interpreter crash is also
still open.

Eight seeded logical games, repeated across sixteen executions, covered both
seat orders of Control/Tempo, Tokens/Ramp, Midrange/Drain and Tribal/Burn. All
complete identity-sensitive results matched; no game timed out or logged
cast-time cost/target rejection. See [compact results](ai-recurring-payoffs.json).
This is a repeatability smoke, not a win-rate or expert-play study. Feature
decision evidence comes from the canonical board fixtures, not these match
outcomes. Both LAN endpoints returned HTTP 200 after validation.

## Known Limitations and Next Upgrades

The reward parser remains a bounded heuristic, not arbitrary Oracle semantics.
It does not model all activation costs, conditional rewards, suppressed
abilities, resource engines or future opportunity frequency. Death eligibility
uses currently public creatures, not predicted hidden cards.

The destruction safeguard covers fixed-cost printed mass destruction, not all
targeted removal, variable costs, exile, alternate costs or opponent responses.
Unknown is not safe, and the unanswered projection is not adversarial search.
Gameplay support and browser acceptance for newly interpreted abilities must
be tested independently. Larger decision-quality and latency samples remain
necessary before claiming broad competitive AI strength or balance.
