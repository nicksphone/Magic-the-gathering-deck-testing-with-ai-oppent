# Current Transform-Draw Wording

The complete pinned official Corruption of Towashi object uses "a permanent you
control enters transformed." The shared transform-draw recognizer previously
accepted only the older "a permanent enters the battlefield under your control
transformed" word order. Replacing the reduced day/night fixture with the actual
record therefore exposed a real missing-trigger regression, not an incorrect
trigger-order expectation.

The production correction changes only that selector alternative in
`rules_engine/events.py::TRANSFORM_DRAW_RE`. The draw instruction, optional
choice, once-on-accept key, controller checks, collector, event publication and
APNAP behavior remain unchanged. There is no card-name branch. Restoring the
previous regex string restores the entire module's bytes and AST.

## Observed Qualification

One declaration runs 14 whole modules. Before the parser correction it reports
132 passes and seven failures in 13.47 seconds: the original simultaneous
day/night APNAP case and six new current-wording admission/choice cases. After
the single production correction, all **139 cases pass in 13.47 seconds**, with
zero failures, errors or skips. Original test identities and assertions remain;
the independent deck-metadata correction changes only the first Fire // Ice
face-name expectation to the genuine `Fire`.

The cohort includes the 35-case deck-service component, the 28-case numeric
transform component, the 46-case day/night fixture component, six original saga
cases and 24 new wording controls. These are constituents of the one 139-case
run, not additional results to add to it. The earlier fixture-only 45-pass,
one-failure HOLD remains preserved as historical evidence; it is resolved only
in this tested composition with the generic parser correction.

New controls exercise real transform-effect dispatch and optional public choices
for both seats, current and explicit legacy wording, opposing-control exclusion,
decline versus acceptance, and snapshot restoration before subsequent transforms.
Negative grammar vectors retain the selector, reward and frequency boundaries.
They are declared diagnostic mutations, not purported canonical card facts.

A pre-import native audit hook denies SQLite connections through all three
tested aliases, sockets, child execution and external-AI imports. All seven
canaries reject; no unexpected denial, database, thread, child or descriptor
delta remains. Runtime files and existing source bytes match before/after each
gate. The RED run generates ten owned placeholder/token SVGs; GREEN reuses them
unchanged. This is not a cold-cache or whole-fileset-unchanged claim.

## Boundaries

The canonical records and complete face lists are independently captured at the
actual fixture-consumption seams. The tests use trusted positioned battlefield
fixtures; this is not an HTTP, real-cast provenance, native-browser, whole-backend
or AI-strength certificate. The recognizer's existing search/substitution and
unrelated instruction grammar are not redesigned or exhaustively certified.

Phase 1 remains open for the remaining handwritten-data scope and later whole
hosted acceptance. The separate `6900e9d1` browser job failed while its backend
job was still running; neither is represented as a whole-source pass here.
