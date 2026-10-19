# Friendly Damage Materialization Safety

## Frozen Scope

Qualified against `19a925291364f08547f06dd55fc8344e14fe8c6f` plus the
unchanged natural Heat diagnostic increment `f2e47c1cb26385695436e569b008c23d0e83e8d92582407f84f55004d65fff16`.
Only `AIAgent._materialize_action` changes and `_harmful_friendly_damage`
is added. The entire module AST outside those two seams equals its preimage.
No scorer, engine, events, cost, API, UI, Oracle, search cap or budget changes.

After existing cost/target materialization, admitted fixed or conditional
single-target damage to a friendly permanent reuses `friendly_destruction_profit`.
Known profitable choices remain valid. When that forecast is unknown, the
checked engine projects only the announced spell, stopping before older
stack items, choices or unresolved death payoffs. It rejects a proved departure
with a lower actor board evaluation, only when private resource continuations
remain untouched. It neither reads hidden library identities nor assumes an
opponent inspection choice. If available, canonical opposing target hints are
ranked using existing threat valuation and the redirected action is checked.
Otherwise the existing invalid-choice marker excludes the action from response,
strategic ranking and proactive pass-loop paths.

## Qualification

All 171 focused assertions pass ordinarily in 28.54 seconds, without exclusions:
unchanged original audit 27 (desired policy RED plus all 26 controls), additional
controls 22, unchanged five neighboring modules 122. The additional cases cover
both seats, response/proactive windows, admitted Delirium damage amounts 2/6,
actual six-toughness lethality, canonical Lightning Strike sibling damage,
opposing target redirection, nonwinning pending death payoff preservation,
root purity, snapshot restoration and hidden-hand/order invariance. Existing
Bastion of Remembrance and Blood Artist controls preserve useful friendly lethal
removal across Tempo and Aristocrats. Fixtures and original witness are unchanged.

The exact captured actor remains master/Tempo/opponent Control with its saved
empty pass-memory. Five unprofiled cold actors per version yield median direct
choose latency 0.012236s original / 0.186007s fixed; checked application medians
0.029699s / 0.014170s. Original chooses damaging its own creature; fixed chooses
pass. This added work is a local correctness cost, not a global performance
improvement or an API/game-completion measurement. The separate instrumented
Blue run exited 139 incomplete; no timeout cause is attributed here.

## Reproduce

The archived source includes the unchanged diagnostic helper/test dependency.
Use a local private copy of the sealed synthetic witness, never a live database.

```sh
cd backend
export PYTHONPATH="$PWD"
export MTG_HEAT_WITNESS=/local/evidence/sealed-self-removal-witness.json
export MTG_HEAT_REPORT=/local/evidence/rank-diagnostic.json
/home/nick/.hermes/cache/scratch/mtg-qualified-python-AIHCn3/bin/python -m pytest -q \
 tests/test_natural_heat_target_audit.py tests/test_friendly_damage_materialization.py \
 tests/test_self_removal.py tests/test_ineffective_destruction.py \
 tests/test_pending_removal.py tests/test_ai_recurring_engines.py \
 tests/test_ai_destruction_reuse.py
```

## Limits

Qualification is the admitted single-target spell damage kernel, not all
friendly interactions, divided damage or activated abilities. Existing parser
support for Delirium is used unchanged; fetched authentic Fiery Impulse and
Galvanic Blast raw records are investigation evidence only, since their
Spell Mastery/Metalcraft clauses are not admitted by this frozen interpreter.
Unresolved payoffs/choices/resource acquisition abstain rather than guess.
No blanket card-family certification, hidden-information expansion, future
opponent prediction or full-suite/game-finish claim is made. Parent composition
against its newer branch remains a separate gate.
