# Matched Trigger Context

Production scope is events.py only: the self-cycling branch of
_collect_triggers, _trigger_from_oracle, and the adjacent
_matched_cast_trigger_clauses helper. Ordinary spell filtering and the generic
token descriptor hook are frozen predecessors, not rewritten here.

For a single recognized eligible cast/copy trigger clause, compilation uses
that clause rather than unrelated Oracle paragraphs; generic fallback compiles
its instruction while retaining the original clause for contextual targeting.
Controller, causing spell identity, effective spell types and cast-vs-copy
predicate are checked. Existing specialized cast instructions keep their full
matched clause. A matched paid optional reward stays explicitly unsupported.
The trigger owner and the causing spell remain distinct source identities.

A targeted self-cycling instruction retains __trigger_resolution_text and its
original __trigger_full_clause, so the existing public target selection path
binds a legal target at stack entry. No target is guessed when none is legal.
Existing human target requests, automatic non-human target policy, protection,
hexproof/shroud checks, pending-choice resume and payload resolution are reused.

This is not a new parser for arbitrary cast restrictions, intervening-if clauses
or multiple separately matched cast abilities on the same source. These retain
legacy handling, not a newly certified or silently flattened ability sequence.

Canonical qualification keeps all original43 assertions unchanged. Additional
checks cover explicit private HTTP target choice, Thunder/Roar source colors,
rejection immutability, restart, no legal targets, Talrand/Shark separate sources,
actual Disenchant response and trigger survival with each causing cast's own
mana value. Cast/copy notification tests are event-routing controls, not a
played copy-spell claim. Paid optional support is still a separate backlog.

The specialized create_shark_token handler independently drops printed blue
color. A separate strict report-only repro is retained under audit-tests;
no handler, descriptor, Oracle or balance adjustment is included in this fix.
