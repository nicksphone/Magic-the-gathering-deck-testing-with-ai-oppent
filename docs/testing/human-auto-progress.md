# Human-versus-AI Automatic Priority Flow

## Contract

The legal-move endpoint exposes optional boolean `can_auto_pass`, evaluated by
the same human-pause policy as autoplay and bound to its revision and acting
seat. The UI only automatically crosses human windows in player-versus-AI.
Missing flags from older servers conservatively keep human control. Existing
mutation coordination, revision checks, pause/recovery and error handling apply.

Meaningful spells, lands, non-mana activations, attack/block decisions and
required choices stop progression even outside configured stop steps. Mana
activations alone, unavailable-action hints and a blocking roster without any
available creatures do not require a click. Human-versus-human retains its
manual flow and configured autoplay filters.

Untap has no priority. Turn draws run through the existing rules engine; this
feature adds no draw or phase operation. Payable instants preserve end-step,
upkeep and draw windows. Mana is still cleared by engine step transitions;
there is no invented response window before untap or carry-over mana rule.
Existing stack response countdown and hold controls remain; required choices
without a legal pass cannot be auto-passed by that countdown.

## Validation

Run the focused backend tests in an isolated tracked-source copy, because
existing API tests write local SQLite. Frontend commands:

```sh
cd frontend
npm test
npm run lint
npm run build
cd ..
MTG_KEEP_TEST_ARTIFACTS=1 bash frontend/tests/run-browser-ci.sh browser-auto-progress.mjs browser-recovery.mjs
```

The real-browser test resumes a constructed canonical rules position, crosses
untap/upkeep/draw automatically, checks exactly one drawn card, and observes an
unchanged revision after reaching a legal land. Separate payable Think Twice
positions preserve human priority and mana in opponent end-step and draw
windows. These are constructed regression positions, not competitive matches.
Backend regressions cover both seats, meaningful action types, bare mana,
restricted hints, no-blocker progression and actual untap/draw engine flow.
The final isolated backend selection passes 126 checks, including payable
end-step instants using either pooled mana or two untapped Islands, both seats,
existing priority-stop behavior, opening hands, cleanup and draw restrictions.
Frontend unit/contracts, hooks lint and the production build pass. The focused
automatic-flow and recovery browser scenarios pass.
The complete browser harness also passes, including restart/ambiguous-write
recovery, sideboarding and natural BO3 in AI/AI, human/AI and human/human modes.
The 126-check backend selection is not a new full backend-suite qualification.

The full browser harness includes this scenario. It additionally exercises
both-seat action/choice flows, recovery, writes and natural BO3. This is not
arbitrary-card certification or a long-session LAN/accessibility review.
