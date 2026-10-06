# Mechanic Control Warning Gate

`Controls` recognizes its existing mechanic-control kinds before choosing a
dispatch branch. An unknown or missing kind produces a `role="alert"` warning
and no mechanic submission control. The guard also precedes the `__none__`
shortcut, so a sentinel cannot make an unknown kind actionable.

The guard includes all existing frontend kinds and the engine's generic
`foretell_from_hand`, `choose_revealed_discard`, `choose_revealed_exile`, and
`linked_exile_copy` choices. Existing supported branches, selections, targets,
costs and callbacks are unchanged. The API parser remains forward-compatible:
this is a UI capability warning, not a backend/card-support certification or a
new wire schema. The engine remains the action-validation authority.

## Focused Checks

The standard `npm test` also runs the focused manual-mana, mechanic-control and
Suspend checks. Set `MTG_TEST_PYTHON` to the installed backend environment; these
component checks use local canonical engine views, not the live database.

From a frozen isolated Git checkout with external dependencies:

```sh
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python \
node --experimental-strip-types frontend/tests/mechanic-control-warning.mjs
cd frontend
npm run lint
npm run build
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python npm test
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python npm run test:unit:suspend
```

The component check uses real canonical Otherworldly Gaze surveil views for
both seats. It compares supported control markup with a Git baseline and
checks unknown/missing kinds, including sentinel options. It also inventories
explicit pending-kind dispatches from the backend, preventing engine-supported
generic selections missing from the TypeScript union from being overlooked.
Kind-only protocol variants are component seam probes, not fabricated cards or
claims that their synthetic combinations are legal game states.

Set `MTG_MECHANIC_BASELINE` to the pre-fix Git revision for an explicit before/
after markup comparison. Without that setting, it uses the current source file;
ordinary warning/control checks therefore also work from a source archive without
Git history. That mode does not claim historical markup parity.

## Actual App Gate

The separate, unchanged test-only diagnostic dependency provides:

```sh
MTG_TEST_PYTHON=/path/to/external/backend/.venv/bin/python \
MTG_FRONTEND_DEPS=/path/to/external/frontend/node_modules \
bash frontend/tests/run-ui-action-diagnostics.sh
```

It runs 16 checks in both seats with real HTTP and the actual App. Unsupported
mechanic probes must now show a warning with no confirmation and zero action
POSTs. Canonical casting, held human response, surveil choices/order, reload,
private hand/choice views and malformed-contract rejection remain covered.
Synthetic unknown kinds are explicit wire faults, never invented Oracle data.
The runner requires a frozen clean tracked product source and local runtime;
local evidence storage fails closed without mounted writable NFS. Ports are
random loopback ports excluding 10199/15173/19222. It does not run shared CI.

Relevant unchanged regressions additionally exercise actual-App discard/
sacrifice and target choices, AI hand/control privacy and held HTTP response
controls (`browser-ui-v2-costs.mjs`), plus the existing human-action component
browser script on the same dedicated services. No fixtures or drivers change.
These are bounded consumer gates, not blanket card or mechanic certification.
