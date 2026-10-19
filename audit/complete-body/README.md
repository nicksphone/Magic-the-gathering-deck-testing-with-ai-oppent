# Complete Printed-Body Regression Tests

Run with the project's installed backend dependencies from the repository root:

```sh
python -m pytest -q audit/complete-body
```

These are complete test modules, not selected node subsets. They cover complete
raw-body admission, malformed suffix rejection before payment, actual paid
canonical interactions, target/source incarnation, basic-land replacement,
loyalty abilities and their continuations. Canonical JSON and provenance are
preserved. Synthetic grammar variations are identified separately in the tests.

Original assertion bodies are retained except one explicitly strengthened
ten-case loyalty witness. Its historical version required an unsupported cast
to succeed before testing activation rejection. The repository version instead
checks public and direct cast rejection before payment, then pays for a complete
canonical card and tests an explicitly injected legacy battlefield surface for
atomic activation rejection. This is not a gameplay text-changing effect. The
unchanged historical witness and its ten early-rejection failures are archived.
Two module-level source path assignments use the repository layout instead of
temporary worker checkouts. The conftest supplies imports and pytest-owned evidence;
set GAP6_EVIDENCE to retain detailed action transcripts elsewhere locally.

These tests do not certify every Magic card, browser play, expert AI, or release
readiness. Neighboring backend modules are qualified separately in the linked
composition report. Test counts overlap earlier worker cohorts; do not sum them
as independent coverage.
