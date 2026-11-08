# November 8 canonical stock for modal-spell fixtures

The shared modal-spell fixture now gives `MatchFactory` the complete pinned
official Mountain object, adding only `card_name` and the original quantity 32.
Both physical seats retain the same stock, seed 7134, spell sample seed 7135
and scene setup. The old row supplied a handwritten type line and empty Oracle
text. No production code, shared loader, official data or original assertion
changes.

The existing Factory reads top-level card fields. This fixture therefore uses
`canonical_positive_fixtures.raw_card` directly, matching its existing direct RAW
spell-sample pattern. The hydration-service `card_metadata` wrapper is not a
Factory input adapter. The pinned source has sixty fields; its entire object
reaches the native input boundary without printed-fact overrides.

## Observed qualification

The corrected private witness reports four expected assertion failures on
unchanged source, then four passes on the candidate. It observes the actual two
Factory deck inputs and the native Oracle and retained physical Oracle facts
of all 64 Mountain instances. These are static fixture constructions, not AI
decisions or natural games.

One declared command then runs all five complete affected modules:

| Whole module | Ordinary passes |
| --- | ---: |
| `test_incendiary_modal_root.py` | 49 |
| `test_incendiary_modal_boundaries.py` | 36 |
| `test_incendiary_modal_lifecycle.py` | 58 |
| `test_mode_target_native_schema.py` | 40 |
| `test_modal_targetless_announcement.py` | 162 |
| Combined execution | 345 |

The command has zero failures, errors or skips. JUnit time is 12.985 seconds;
guarded runner time is 13.269 seconds and supervisor time 14.003 seconds.
All 179 original assertion ASTs and parameter/function ASTs remain, apart from
the stock assignment itself. Removing the one import and reversing that one
assignment recovers the original file byte-for-byte. The four consuming modules
are unchanged.

The source base is `28e3585a2a25424648cb49c1611bcdc11102ccf3`, with exactly that
one test-file overlay. Both frozen packets contain 5,130 public regular files;
SHA-256 and recorded Git blob IDs verify. The shared RAW JSONL retains SHA-256
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.
The Incendiary Command object and every other source/data file remain unchanged.

Actual execution records show no denied IO attempts. SQL, sockets, children and
OpenAI imports are forbidden before test collection. Twelve exercised guard
controls cover native/public SQLite constructors, both socket aliases, process
creation, system commands, protected-name synthetic fixtures and OpenAI import.
No real protected artifact body is read. All five execution epochs close their
owned process groups normally; the whole original-module cohort runs once.

## Retained witness correction and scope

The first private witness used `printed_characteristics` for its fourth check.
That legacy restoration map is normally empty at birth; the native retained
facts live in `characteristic_record['physical']`. The first baseline reports
four failures and the first candidate three passes plus that witness failure.
Both records are retained. The corrected witness separately fails all four
checks on the old source and passes all four on the unchanged candidate.
No production or fixture correction was added to satisfy the mistaken check.

The original guard-control versions remain bound to their exact saved harnesses.
The current audit function's AST is identical; those controls are not represented
as exercising the later witness assertion. A final metadata/source auditor
checks the actual source delta, all results, version bindings and closure without
runtime IO or protected-body reads. Independent final review approves this
bounded correction without findings.

The exploratory direct-literal census found twenty candidate text mismatches
across sixteen files for the 155 seed names, including deliberate negative and
protocol inputs. That is not an exhaustive inventory: indirect Factory inputs,
other card names and generated/parser data still require reconciliation. This
finite positive correction does not waive those inputs or complete Task 1.3,
Phase 1, AI-strength, full-backend, hosted CI or RC acceptance. Private evidence
remains under `/home/nick/mtg-rc-evidence-20261108/canonical-modal-stock`.
