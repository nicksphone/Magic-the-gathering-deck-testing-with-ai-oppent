# Third-Party Notices

## Magic Engine Evaluation

The following projects supplied the executable card knowledge used in our
external-engine evaluation. Their work is credited here and beside its use in
the evaluation source. The original upstream copyright headers and licenses
were retained. We did not author their engines or card implementations.

### Forge

- Authors: the Forge Team and Card-Forge contributors.
- Source: <https://github.com/Card-Forge/forge>.
- Evaluated revision: `61e9442c433711a82258daca3236f936a1d6f70e`.
- Upstream source headers specify GPL-3.0-or-later; its GPL v3 license text is
  retained in [the evaluation's Forge LICENSE](tools/engine_evaluation/forge/LICENSE).
- Our original Forge compatibility tests, native match/search, naming and actor-boundary
  prototypes are separately marked GPL-3.0-or-later
  and explicitly acknowledge the upstream engine and test helpers.
- The local process bridge also includes four modified Forge native input
  classes under `tools/engine_evaluation/forge/native-ui`. Their original notices,
  module license, modification notices, exact upstream source hashes and patches
  are retained. See [their NOTICE](tools/engine_evaluation/forge/native-ui/NOTICE).
- The opt-in Python session owner and React table also explicitly credit Forge
  beside their use. They transport native views and choices; the upstream
  rules, card scripts and Default AI are not our implementations. See the
  [app integration scope](docs/testing/forge-app-session.md).
- The isolated native-AI visibility/cost/mana patches and compatibility tests also
  credit the Forge Team, pin the upstream source preimages and retain modification
  notices, and are marked GPL-3.0-or-later. These are our modifications to their
  existing AI, not an AI or card implementation authored from scratch here.
  See [the native-AI notice](tools/engine_evaluation/forge/native-ai/NOTICE.md).
  The separate linked-damage and targeted-draw changes likewise retain full
  Forge source preimages/postimages, original headers and GPL text. See their
  [combined scope](docs/testing/native-linked-draw-ai.md); the upstream rules,
  card programs and baseline AI remain the Forge contributors' work.
  The separate [known-mana increment notice](tools/engine_evaluation/forge/native-ai/known-mana/NOTICE.md)
  identifies the three modified upstream AI sources and their retained headers.

### XMage

- Authors: the XMage contributors; the original MIT copyright notice names its
  copyright holder and is retained without modification.
- Source: <https://github.com/magefree/mage>.
- Evaluated revision: `987fd4e9c73e9f113e235f8d8f98628f2d391667`.
- License: MIT. See [the unchanged upstream license](tools/engine_evaluation/xmage/LICENSE.txt).
- Our original compatibility test identifies its upstream engine, revision and
  license; it is not represented as an upstream-authored test.

### Scope

These include evaluation sources, four native input modifications and an opt-in
host integration, not a bundled complete engine or card-script distribution.
The running application has not
been switched to either project. The application's
root Apache-2.0 license does not relicense separately licensed evaluation files
or upstream software.

Any adopted component must retain its own copyright/license notices, identify
our modifications and receive a distribution/source-availability review. A
README credit or source comment alone is not the complete licensing process.

Oracle text, card artwork and other card-data sources retain their separate
provenance and applicable notices; software-engine licenses are not a blanket
relicensing of those assets.
