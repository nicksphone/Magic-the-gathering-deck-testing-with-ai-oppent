# Attribution And Bounded Follow-Up

The Forge Team/Card-Forge contributors authored the native engine, AI, controllers,
cost implementation, test helpers and card programs used here:
https://github.com/Card-Forge/forge, revision
`61e9442c433711a82258daca3236f936a1d6f70e`.
Retain [Forge's original GPL v3 license](../../LICENSE), native source headers,
and repository [third-party notices](../../../../../THIRD-PARTY-NOTICES.md).
The original follow-up test and launcher are GPL-3.0-or-later.

`canonical/elvish_spirit_guide.txt` is the complete byte-identical original native
card program at `forge-gui/res/cardsfolder/e/elvish_spirit_guide.txt`, including
its full native Oracle field. The other complete native card programs are the
unchanged Fog, Forest, Craw Wurm and Jace Beleren sources in
[the preceding audit's canonical fixtures](../NOTICE.md). The launcher compares
all five to the pinned native sources before execution. Actual cards are born
through upstream `AITest`/`Card.fromPaperCard`, not substitute rules.

This work only traces and tests the known-Fog/hidden-ESG affordability channel.
It does not modify the frozen candidate patch, the original nine files, the
candidate's ten files, any native production body, K, Q, application/store code,
or parent graph. Printed starting loyalty, tapped land state and Fog-only native
reveal memory are labelled constructed test poses, not natural play histories.
No production, application or save-compatible build identity is established.
