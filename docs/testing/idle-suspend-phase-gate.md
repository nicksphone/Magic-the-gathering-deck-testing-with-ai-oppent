# Idle Suspend Phase Gate

`AIAgent.choose_action` still starts with its ordinary privacy projection. When
the chosen action is pass, it now calls the idle Suspend policy only during a
main phase. The policy already returned no action outside those phases, but
previously performed another complete state projection before that rejection.

This does not introduce a no-Suspend-option shortcut. On an eligible main phase,
the original hand scan and its knowledge-usage accounting still run. The direct
idle Suspend API, timing rules, privacy projector, selected actions and trace
format are unchanged.

## Regression Evidence

Six native regressions use both seats and complete pinned canonical deck inputs.
They compare the exact original caller with the candidate, including action,
reasoning, knowledge counts, unsorted full trace bytes, full agent state, offered
moves, root state and global RNG. The baseline caller is reconstructed by
undoing only this condition and checking its complete function hash.

- Before the change: four off-main cases fail only their duplicate-projection
  count assertion; both eligible main-phase controls pass.
- After the change: all six cases pass unchanged. DRAW and END_STEP cases each
  execute one projector instead of two; main-phase cases still execute two.
- The existing first privacy projection is neither moved nor bypassed.
- Source, descriptors, Python and OS threads, child processes, anchored native
  lock and systemd unit/group closure are checked under the bounded native role.

These are controlled fixture poses, not paid natural games or a complete AI
matrix. The count reduction is not a timing speedup estimate, strategic
improvement, deadline closure, relaxed trace limit or RC certificate. Full
hosted predecessor/module/node/outcome CI is separately required.
