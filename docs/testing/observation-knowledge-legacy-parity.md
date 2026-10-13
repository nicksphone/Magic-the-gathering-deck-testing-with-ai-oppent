# Observation Knowledge And Legacy Parity

Base: published `837bf5137a2adaa62a32942ccbde15a568c43545`.

Observed card records use `asdict(CardInstance)`, which adds the new default
`knowledge_snapshot={}` even when no canonical knowledge was attached. Live
observation and reconstruction require that field's default, but its redundant
serialized presence differs from retained historical observations. The card
serializer already omits an empty knowledge carrier; observation serialization
now does the same, without changing live records.

The correction changes only the observation dictionary expression inside
`serialize_match_snapshot`. It omits only the exact key with a value whose type
is `dict` and whose contents are empty. Nonempty knowledge, malformed values,
other observation fields and all rules state remain present. Deserialization,
observation producers, card models, AI and rules are unchanged.

## Actual Checks

- Three unchanged protected replay modules: **38 PASS / 17 FAIL** on the base,
  then **55 PASS** after the correction. The sealed synthetic input stays
  private and byte-identical; no historical assertion or fixture was adapted.
- The NEW observation module initially collected twelve imported contract
  tests as well as its own twelve cases: **20 PASS / 4 FAIL**, then **24 PASS**.
  Its final module-qualified helper import avoids collecting those imported
  cases accidentally; the contract module is declared explicitly below.
- Final five whole modules, including all protected replay modules, NEW12 and
  the unchanged knowledge contract12: **79 PASS**, zero failures/errors/skips.
  All source bytes and the private input stayed unchanged during execution.

Native SQL, sockets, children and providers are forbidden in these local
checks. The three real preimport denial controls pass. This is serializer/replay
component evidence, not HTTP/storage, measured AI strength or release completion.

Only public tests and code are eligible for publication. The synthetic trace,
raw private replay output and diagnostics are retained in protected archives,
not included in a Git patch or public fixture.
