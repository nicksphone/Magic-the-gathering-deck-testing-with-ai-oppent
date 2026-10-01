# Damage Counter Replacement Increment

## Implemented Scope

Supported infect, wither and printed toxic damage results now use the registered
counter-event resolver instead of bypassing scalar modifiers. The damage source's
controller places counters, including supported last-known-controller data. The
affected recipient chooses competing replacement order. Existing prohibitions
still override placement without converting prevented counters into life loss.
The supported noncombat damage-to-counter replacement uses the same path.

Combat collects simultaneous counter contributions by placer, recipient, kind
and effect provenance before applying modifiers. Multiple toxic creatures do not
each receive a separate plus-one bonus on the same poison-placement event.
Combat's turn-based counter results do not initially qualify for effect-only
Doubling Season wording. Another applicable replacement can make that modifier
applicable; that provenance survives a pause and snapshot restart.

Queued damage counter events preserve their controllers and resume before the
remaining effect continuation. Combat damage events and lifelink resume after
counter choices; state-based actions do not run ahead of the paused event.
Damage batches retain already-dealt lifelink credit through repeated pauses.
The AI's amount-order policy lives in the AI layer, not the rules parser.

## Verification Status

- 176 focused checks pass, including 16 new regressions using existing canonical
  card fixtures and explicitly labeled core-operation setups.
- Frontend lint, TypeScript/Vite build and unit contracts pass.
- Separate isolated HTTP probes pass for the real seat-two combat choice and
  one-tick AI autoplay: human ordering produces four poison counters; AI's
  lower-poison ordering produces three. Both gain the attacker's one life and
  clear the pending choice.
- The complete tracked-source isolated backend suite passes: 2,324 tests,
  292 warnings, 174.01 seconds. The earlier incomplete-copy runs were stopped
  and superseded; they omitted repository documents required by tests.
- Eight seeded seat-paired games reproduce their complete reported game results
  and logs across sixteen executions, with zero timeouts or detected cost,
  target or action rejections. This is repeatability evidence, not AI strength
  or balance certification.
- Graphify's final AST refresh passes: 7,339 nodes, 18,344 edges, 327 communities.
- Full Chromium passes, including the new seat-two combat-counter choice,
  simulation preflight, refresh/process-restart recovery, ambiguous starts,
  sideboarding and natural AI/human controller-mode BO3 flows.
- The first normal-profile rerun exposed fixture leakage: the final fake
  simulator response left a pending start in local storage for later suites.
  Preflight now removes only its simulator keys on exit; original assertions
  remain unchanged. The complete rerun passes.

All test copies use separate databases; the live application database is not
used for these checks. Memory-backed scratch artifacts are not durable across
reboot. Failed/incomplete environment runs must not be reported as acceptance.
Logs and replay artifacts are archived under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/mtg-damage-counter-checks/`.
`/home/nick/Documents/mtg-damage-counter-checks/` is a compatibility symlink;
the two original replay JSON outputs are preserved in `replays.tar.gz`.
[Machine-readable evidence](damage-counter-replacements.json) records source
hashes and artifact hashes. Successful browser runs delete their generated
checkouts/profiles by default; failed runs retain diagnostic locations.

## Known Limitations and Next Upgrades

- Finish pre-entry counters, costs, Saga turn-based lore and other physical
  placement routes. Existing route-fidelity diagnostics remain intentional.
- General simultaneous noncombat damage, mixed placer/multi-kind event ordering,
  competing damage prevention/replacement ordering and their provenance require
  further integration. Do not infer those semantics from this combat increment.
- Granted/removed numeric toxic values, arbitrary counter-added triggers, caps,
  proliferation, counter movement/spending and layer dependencies remain open.
- Amount-based AI is not full resource valuation, expert play or balance proof.
- Disk exhaustion was resolved by removing 730 inactive MTG scratch directories
  after preserving diagnostic evidence. The live databases, uncommitted work and
  the checkout used by active test processes were preserved. About 11 GB was
  reclaimed; archived evidence lives on RCHFiles rather than the SSD.
- Live backend and frontend checks return HTTP 200 on ports 9999 and 5173;
  the recovered backend binds `0.0.0.0`. Long-session/LAN review remains manual.
  No card text, printed stats or deck balance changed.

Rules basis: Wizards' [Comprehensive Rules](https://magic.wizards.com/en/rules)
(120.3, 120.4 and 614.16) and the single-event toxic ruling in
[Phyrexia: All Will Be One release notes](https://magic.wizards.com/en/news/feature/phyrexia-all-will-be-one-release-notes).
