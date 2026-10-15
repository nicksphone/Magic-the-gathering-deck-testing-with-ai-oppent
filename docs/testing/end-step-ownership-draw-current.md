# Ownership-Conditioned End-Step Draw

This bounded generic family supports a complete Oracle paragraph of the form
"At the beginning of your end step, if you control N or more permanents you
don't own, draw M cards." Number words and decimal counts use the existing
number vocabulary. It is not a card-name dispatch or a whole-card support claim.

The collector checks the actual source controller's end step. It counts unique
battlefield objects actually controlled by that player whose actual owners are
other players. A false condition publishes no trigger. The real trigger frame
retains its controller; ability copies use their actual copy controller.

At resolution entry the same ownership condition is checked once. The existing
replacement-aware `draw_cards` handler then owns per-card restrictions,
replacements, choices and continuation queues. Those queues do not reevaluate
the intervening if. A source leaving the battlefield or changing controller
does not retarget or cancel an already-published ability.

Compilation is anchored to the complete raw paragraph, before reminder text
removal. An unknown ownership-family suffix is explicitly unsupported, not a
partial draw. Unrelated conditional end-step families retain their existing
dispatch; this change does not certify those conditions.
Separate unconsumed own-end-step paragraphs still use the existing trigger
parser. A compound ownership paragraph is not split into partial rewards.

Rules references: [Comprehensive Rules effective September 25, 2026](https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt),
603.4 and 608.2a (intervening-if checks at triggering and resolution), and 113.7a
(independence of the ability from its source). The date and references were
verified by the integrating parent; this component did not fetch new rules data.

`test_end_step_ownership_draw.py` uses full committed canonical facts, genuinely
paid casts, checked priority/turn transitions, actual triggers, counters and
snapshot/replay. Its unchanged 23-case baseline was 14 failures and 9 passes;
the first implementation passed those same 23 cases. The separate
`test_end_step_ownership_draw_guards.py` exercises grammar boundaries, actual
source-control changes, actual paid ability copies, and replacement resumes.
These are constructed rules fixtures, not natural games or AI quality data.
No production SQL, socket, provider, chooser or matrix execution is involved.

## Initial Component Qualification

Over the isolated `92a59e11` archive plus this increment, the final thirteen
whole modules pass **122 cases in 460.61 seconds**, with no failures, errors or
skips: the unchanged 23 original cases, 34 guard cases and 65 existing cases.
Source hashes remain equal during that run, with no unexpected I/O. Independent
review confirms the corrected separate-paragraph dispatch. Earlier fixture
failures and the strict mixed-ability regression remain preserved, not relabelled.

Verified private evidence is under
`diagnostics/ci/20261015-ownership-endstep-122PASS-CLEAR-JeHVEG/` on RCHFiles.
This is not an HTTP/SQLite, all-card, final hosted-CI or release certificate.

## Mixed End-Step Routing

The later correction routes this family before the older each/own precedence
chain. It preserves that entire chain when the ownership domain is absent;
otherwise, eligible separate each-end-step and own-end-step paragraphs retain
their independent effects. Unsupported compound paragraphs never receive a
partial legacy draw, including on an opponent's end step.

The new whole module first records 20 failures and 20 passes. With the minimal
two-file correction, it passes all 40 cases. The final fourteen whole modules
pass **162 cases in 476.36 seconds**, with no failures, errors or skips: all
122 earlier cases plus those 40 controls. Source hashes and the existing
compiler, ownership predicate, draw resolver, registry and original test bytes
remain as recorded by the scoped inverse proofs. Independent static review
is CLEAR. The initial 122-case result is not retroactively relabelled.

The added controls declare synthetic initial ownership boards and use checked
phase/priority transitions and actual published triggers; they are not natural
games or fabricated event/stack receipts. This closes the measured each/own
dispatch defect, not arbitrary-card, HTTP/browser or full release acceptance.
