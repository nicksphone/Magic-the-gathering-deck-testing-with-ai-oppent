# Known-Mana Increment Notices

Original native engine, AI, controllers, cost/mana algorithms, test helpers and
card programs are Forge Team/Card-Forge work:
https://github.com/Card-Forge/forge at
`61e9442c433711a82258daca3236f936a1d6f70e`.
Retain original native headers, [Forge's GPL v3 license](../../LICENSE) and the
repository [third-party notices](../../../../../THIRD-PARTY-NOTICES.md).

The patch, explicit build/test callers and additional controls are separately
GPL-3.0-or-later. Modification date: 2026-11-06. Only ComputerUtil.java,
ComputerUtilCost.java and ComputerUtilMana.java are changed in an owned copy.
The frozen identity patch is applied unchanged before this new delta; neither K,
Q, the old candidate, original tests nor parent profile builder is overwritten.

The new delta introduces per-call knownCard overloads, filters candidate source
identities before reading mana abilities and filters three hand-statistic/color
inputs. Legacy unrestricted owner calls and actual payment keep native rules and
costs. Additional-cost/global/conditional-script knowledge limitations remain;
this is not a whole-engine fairness or application/save qualification.

All real-card definitions used by the tests are complete unchanged native card
programs retained in the preceding audit folders. In particular the full ESG
program is in ../../ai-boundary/hidden-mana-followup/canonical and its provenance
is documented there. The test runner byte-compares all native programs. Cards
are born through native AITest/Card.fromPaperCard, not substitute rules.

The separate new test file is in
../../ai-boundary/hidden-mana-followup/known-controls/NativeKnownManaControls.java.
Its printed starting loyalty, tapped land state, native reveal callbacks and
controlled combat/payment poses are labelled test setup, not natural histories,
full matches or winner assignments. Native paid casts are not strategy labels.
