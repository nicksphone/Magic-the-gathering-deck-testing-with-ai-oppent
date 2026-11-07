# Native Own-Library Bottom Selection

This is a modification of the **Forge Team/Card-Forge contributors' AI**,
not a new engine, card database or trained model. Original helpers and complete
card programs remain upstream work under the supplied GPL-3.0-or-later notices;
see `NOTICE`, `LICENSE` and the attribution in the changed source.

## Correction

The generic Dig selector previously returned its best-card helper regardless of
whether the chosen card was being retained or put on the library's bottom.
For empty `AILogic`, self activation and self related player, a `Library`
destination with default or explicit `LibraryPosition=-1` now selects the
existing worst-card helper instead. Hand/top destinations, special hints and
the old opponent branch keep their previous paths.

That discard-oriented helper can return null after filtering protected
permanents. A native mandatory-minimum reproduction exposed this with unchanged
Illusions of Grandeur and Bolt metadata. The fallback now uses the existing
cheapest-card helper over the original offered collection, not the filtered
empty subset. No new card-name branch, card-program edit, hidden-state read,
resource mutation or random choice is added.

This is a destination-direction correction, not a complete joint hand/exile
planner. It does not close opponent-activated/special-hint variants or certify
every card's strategic value. It is not restricted to a named source card.

## Executable Checks

- `NativeDigAllocation4`: two seats, actual ordinary Iteration selection and UR
  payment, a genuine earlier land play, then ordinary AI selection and R payment
  for an exiled Bolt. Two separate manual allocation rows establish the legal
  alternative; they are not reported as AI success. The exact registered main
  lists are in `inputs/`.
- `NativeDigDirectionControls`: twenty labelled internal selector-protocol rows
  for hand, top, bottom, opponent, hint and null-related-player boundaries, with
  ordered-input/parameter and serialized-RNG checks. Synthetic ability strings
  are protocol controls, not new canonical card text.
- `NativeDigMandatoryChoice2`: two native controller min1/max1 calls with stock
  protection metadata. It checks an actual returned card rather than only
  calling the policy helper. It does not resolve or certify Illusions' gameplay.

These are controlled fixtures, not naturally drawn games, expert labels or
strategy-strength estimates. `QUALIFICATION.json` records the separately executed
groups, retained baseline failures and final prefix identities. Private game
journals and model requests are not public fixtures.

## Build And Identity

`dig-direction.patch` changes the pinned `DigAi.java` preimage only. It is an
incremental composition over the corrected fourteen-source/twenty-three-class
parent, not a replacement for all prior native AI corrections. Source/class
pins are in `SOURCE-PINS.json`; `PAYLOAD.json` is the strict schema12 closure.
Exact vendor pre/postimages and unified-diff context retain upstream whitespace;
the local attributes file limits whitespace exceptions to those three files.

Compile the changed source against that full pinned native classpath with the
existing guarded toolchain (`--release 17`, no implicit source compilation).
Inherit every other source/class byte unchanged, add the Dig source/class, and
derive a fresh profile with `../runtime_profile.py`. Schema12 accepts exactly
fifteen sources and twenty-four physical classes; all older schemas retain
their old required membership. The profile tests use labelled synthetic files,
not pretend compiled Java classes.

Compile the three probes separately into a test overlay and run their `main`
methods under the existing bwrap/JNI/kernel guards and fresh private output
directories. Allocation takes input/output directories; the two protocol probes
take only an output directory. This package does not bypass native guards or
provide a command that silently starts the live application.

Content identity is path-independent; derived runtime/operator identities also
bind their actual local classpath/launch. Never relabel an old profile or save,
or treat a test overlay as an approved runtime. Full application/BO3 adoption,
root-candidate tracing, broad fairness and playing strength remain separate.
