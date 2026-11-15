# Burn Decisions And Current Hand Inspection

The user reports Burn passing while damage spells remain in hand. Check actual
timing/payment admission before treating every priority pass as a mistake.

1. Preserve the live game read-only. Reproduce the questionable decision from
   the saved seed and public-log prefix in private, isolated evidence.
2. Exclude one-shot face damage from the forced creature-removal shortcut.
   On otherwise equal evaluations, conserve listed spell mana before comparing
   card names in proactive own-main windows. Preserve action-type ordering and
   response-window tie ordering. Value known pending response effects using
   the existing public forecast, without resolving the real/search frame or
   guessing unsupported/hidden-zone outcomes.
3. Verify canonical paid burn, real remaining-mana Suspend, creature removal,
   lethal priority, timing, purity and hidden-library invariance. Run complete
   affected AI modules, not hand-picked passing cases.
4. Keep the opt-in inspector current after committed revisions. Coalesce reads
   without cancelling an in-flight request; retain the labelled previous hand
   while refreshing. Bound automatic catch-up to one read per revision and
   leave errors/manual retry visible. This changes the prior manual-only UI.
5. Run frontend tests/lint/build and native synthetic App checks. Refresh the
   AST graph, archive private evidence, back up the user database and old code,
   and deploy only the changed backend policy and frontend build.

No private game snapshot is a public fixture. No hidden-library peeking,
learned-model training, difficulty change, rules change or forced live action.
Checked comparison lines assume the opponent passes; they are not guarantees
against a response or a claim of general competitive AI strength.

## Verified Outcome

- A seeded private replay matched the first 113 public log entries before the
  inefficient choice. On that same saved position, the old policy picked
  Skullcrack; the corrected policy picked Lava Spike. Checked, unanswered
  branches dealt equal immediate damage, but the cheaper line retained a real
  payable Rift Bolt suspension. None of these private snapshots is in Git.
- Ten complete affected AI modules passed: 382 cases, no failures or skips.
  This includes 28 new controlled canonical/scoring cases, both seats and
  Strong/Master, actual payments/resolution, lethal/removal controls, timing,
  restoration, input purity and hidden-library invariance. The two emitted
  warnings are dependency deprecations. SQL/socket/process audit denials were
  empty; static API definitions imported for existing fixtures, not a lifespan.
- The initial global cost tie-break was rejected by a paid life-gain response
  control. The final tie-break is proactive-only. A pre-existing Master
  response-valuation gap was also reproduced and corrected with the existing
  public-effect forecast, preserving pending search frames and unknown cases.
- Whole frontend tests, lint/build and the native synthetic App browser check
  passed. The hand view now follows revisions with bounded coalesced reads,
  rather than retaining the old manual-only snapshot indefinitely.
- Closed, integrity-checked user-database backups and previous code/build were
  verified on NFS before deployment. Only the AI policy file and frontend build
  were updated; existing games retained their revisions and the debug gate
  remained enabled for this private preview. No live game action was issued.

Historical harness/fixture failures, the rejected intermediate policy and the
diagnostic traceback-process crash remain in private evidence. They are not
relabelled as successful runs. This is not a full RC or AI-strength certificate.
