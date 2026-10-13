# Task 4.2 Interaction-Hold Baseline

Exact source: `2f42a6eb352480fae1940018b70f4395c478c38e`.
This increment adds only NEW tests and this report. All 3126 original files
were byte-equal at the qualified baseline; no scoring or production change
was made. A/B and full-matrix strength remain unmeasured.

## Qualified Whole Module

24 cases: 16 passes, eight strict assertion failures, zero errors/skips,
6.71 seconds. Both seats, snapshot round trips, Control and Counter-heavy:

- Eight actual tier-3 Zulaport Cutthroat casts are genuinely countered with
  a paid Counterspell and complete checked stack resolution: PASS.
- Eight stable tier-1 Llanowar Elves (1/1) cases incorrectly spend a payable
  Counterspell instead of holding it: strict RED.
- Four actual Veil of Summer casts make a subsequent real creature spell
  uncounterable. The AI does not waste Counterspell and actually pays for
  its red Bolt decision. A genuine checked pass alternative then permits
  the actual AI to answer the resolved creature with paid Lightning Bolt:
  PASS. This alternative is not the chosen forward prefix or a reference win.
- Two hidden full-canonical hand variants have identical opaque decision
  views and actions; two tier-3 cases lack the second blue mana and do not
  invent a cast permission: PASS.

The whole module uses existing full seed155 Scryfall bodies, existing
derive/merge/snapshot helpers, real legal menus, actual strong-policy choices,
actual checked payments, real stack objects, and complete stack resolution.
Profiles are SQL-free eligible canonical fixture rows, not database writes.
Trusted starting boards and mana pools are explicitly not paid-birth proofs.

## Source-Supported Cause and Proposed Scope

`ai/agent.py:_choose_action` has an existing low-value creature filter that
preserves Counterspell only when `_stack_item_threat_score` is below 2.
For the genuine tier-1 Llanowar spell it returns 3.8865, so that filter does
not run. Counter ranking and Control cast bias then reward spending the
counter. The eligible printed tier is 1, not the dynamic stack score.
The actual tier-3 Zulaport score is 7.6865 and should remain countered.

Proposed product scope is that existing `_choose_action` filter only, not
new weights or a new planner. Reuse `_printed_major_threat` for semantically
eligible printed low tier; supplement only a demonstrably stable public
context. Preserve dynamic behavior for unknown/stale/malformed snapshots,
suppressed printed abilities, changed effective types, urgent low life,
public battlefield pressure, and higher-tier threats. Printed answer routes
remain advisory: actual legal targets and native uncounterability govern.
Product and new boundary controls belong in a separate increment.

## Retained Development Ledgers

The first 24-case attempt was 12P/12F: eight genuine stable-tier failures and
four NEW fixture failures because the old normalized Carnage Tyrant fixture
is not an eligible complete canonical row. No canonical gate was relaxed.
That incomplete fixture was replaced only in the NEW tests with existing
full RAW Veil and Bolt. No new network intake or user cache edit was needed.

The intermediate Veil cases required an unrequested unconditional pass;
the AI instead played a real red Bolt at the opponent, not Counterspell.
Those 12P/12F ledgers are retained, not labelled twelve counter-policy bugs.
Only that NEW overstrict expectation was aligned to counter-not-wasted;
all eight stable-tier RED expectations are unchanged. The alternative
creature-removal path is explicitly labelled a checked counterfactual.

The launcher installs global SQL/socket/process/provider denial before
pytest/project collection. Three actual native constructor attempts
(_sqlite3, _socket, subprocess) are denied before IO/child creation.
No database is created. This is an audit fence, not an OS sandbox claim.
