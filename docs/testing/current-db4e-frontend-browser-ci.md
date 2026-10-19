# Published db4e Frontend And Browser CI

The later published source `76b0befd7b3aed9365c7a5c5b9d20faafa77ef02`
also has terminal frontend and browser success in run `38973254693`, attempt 1.
Frontend job `117216449877` completed at `2026-10-16T22:03:41Z`; browser job
`117216449626` completed at `2026-10-16T22:28:24Z`, including the original
**Browser action and recovery flows** step. This includes the passive diagnostic
addition and layered-toxic correction. Its backend job is still a separate
pending result; subsequent uncommitted fixture work is not part of that source.

GitHub Actions run `38962147010`, attempt 1, executes exact published source
`db4e0758a5a1d755abc964e7f40b0286783506e5`.

- Frontend job `117179597741` completed successfully at
  `2026-10-16T20:26:40Z`.
- Browser job `117179597326` completed successfully at
  `2026-10-16T21:04:26Z`; its existing **Browser action and recovery flows**
  step succeeded, running `bash frontend/tests/run-browser-ci.sh`.

These are terminal GitHub job/step results, not counts inferred from log banners.
No raw backend log or protected synthetic trace was downloaded. Backend CI was
still running when this record was written and is not declared successful here.

The browser job uses the existing Ubuntu CI configuration, including its existing
`MTG_BROWSER_NO_SANDBOX=1` setting. No sandbox policy, browser action, assertion,
timing budget or workflow was changed for this result. It is not qualification
of the separate sandboxed local Chrome/Brave/Firefox runs, LAN trust, other
platforms, a selected live deployment or the complete release.

The earlier `4f86df95` browser job failed. Its abort cause remains unknown; this
later successful run does not retrospectively explain or erase that failure.
The subsequent passive diagnostic addition has separate unit evidence and is
not included in this published-source CI result. Neither this result nor the
833-case data component signs off the remaining Phase 1 fixture scope.
