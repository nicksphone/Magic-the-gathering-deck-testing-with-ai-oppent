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
- Our original Forge compatibility tests, native match, naming and actor-boundary
  prototypes are separately marked GPL-3.0-or-later
  and explicitly acknowledge the upstream engine and test helpers.

### XMage

- Authors: the XMage contributors; the original MIT copyright notice names its
  copyright holder and is retained without modification.
- Source: <https://github.com/magefree/mage>.
- Evaluated revision: `987fd4e9c73e9f113e235f8d8f98628f2d391667`.
- License: MIT. See [the unchanged upstream license](tools/engine_evaluation/xmage/LICENSE.txt).
- Our original compatibility test identifies its upstream engine, revision and
  license; it is not represented as an upstream-authored test.

### Scope

These are evaluation sources, not bundled game-engine implementations. The
running application has not been switched to either project. The application's
root Apache-2.0 license does not relicense separately licensed evaluation files
or upstream software.

Any adopted component must retain its own copyright/license notices, identify
our modifications and receive a distribution/source-availability review. A
README credit or source comment alone is not the complete licensing process.

Oracle text, card artwork and other card-data sources retain their separate
provenance and applicable notices; software-engine licenses are not a blanket
relicensing of those assets.
