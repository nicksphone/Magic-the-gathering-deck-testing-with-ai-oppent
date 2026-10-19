# Legend Keeper Consumer Context

Qualification base: exact published `7d8877345c5753ffab0640d6bd485284153d12fb`
git archive plus the immutable U9 engine increment and its tests. U9 production
applies cleanly; no whole engine/SBA overlay is used. The published base already
contains the graveyard consumer/emitter/entry dependencies. No later Kozilek fix
is consumed. Engine/source hashes and actual commands are retained in evidence.

Only `TrainingEnvironment.lookup_intent` changes. For the actor's authoritative
`pending_mechanic_choice.kind == legend_keeper`, supplied `legend_group_index`
and `legend_context` must be non-null, actually present in current pending, and
equal under the existing canonical JSON encoder BEFORE legal-view generation,
action completion, or stripping. Unknown/nested-extra/stale context is rejected.
Object-key ordering is immaterial; array ordering and JSON scalar types matter.
The server context is never updated from the request. Canonical equality is the
boundary: indistinguishable identical JSON is not a new cross-state identity
claim, and no new match-ID schema field is invented.

An explicit singleton list `card_ids` containing an offered keeper ID is required
even when display context is omitted. No keeper/index/plan is inferred. Existing
MechanicChoice validation still rejects competing choice payloads. All other
mechanic display/context guards and optional-effect empty display remain intact.
Raw typed/API actions still reject the display metadata; only lookup_intent
returns a strict existing action for checked execution.

NEW tests capture full canonical funded paid Isamaru/Progenitus positions, not
natural-game development. Both seats qualify exact whole-engine context,
projected hints, unchanged caller input/root, and rejection before complete_action.
Tampered pending seams are explicitly trusted negative tests, not causal HTTP
transitions. Fresh-process tests delegate to the unchanged U9 worker with all
its private-view, SQLite, replay and replacement assertions retained. The new
wrapper materializes the actual HTTP whole keeper view, rejects raw view echo
with HTTP422/root/controller/SQL unchanged, then submits the strict action.
Seed/keeper/replacement run in three distinct processes on owned local SQLite;
remote sockets and out-of-root databases are denied.

Immutable U9 public-contract tests contain two historical consumer-rejection
assertions. The new consumer deliberately makes those assertions obsolete;
the unadapted run is retained as a characterization ledger. A separately
authorized test-only acceptance patch replaces only those two expectations with
exact whole-view materialization; projected hint, state purity and wrong actor
checks remain. No original55/completion/restart or raw API assertion changes.
The separate original two Kozilek draw-four failures remain ordinary reds until
their independently owned compiler fix is composed. No UI-complete claim.

Whole private-choice neighbors require the existing source-only isolation marker:
`printf '%s' "$PWD" > .private-choice-audit-source`. The first run's missing-marker
setup errors are preserved; the fixture guard is not weakened or edited.
