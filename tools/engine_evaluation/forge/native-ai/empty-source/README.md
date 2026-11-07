# Empty Known-Source Follow-Up

Forge's engine and native AI are Forge Team/Card-Forge work. Retain the
[original notices](../NOTICE.md), [parent increment notices](../known-mana/NOTICE.md)
and [GPL license](../../LICENSE). This is an additive correction, not a rewrite
or relabelling of the frozen parent candidate `74e0cc8a`.

Review found a direct-overload edge: scoped filtering can reject every supplied
mana ability, after which the retained Treasure preference indexes the empty
list. The bounded app path did not demonstrate this exception; its caller already
avoids an initially empty list. The public scoped API must still handle rejection.

The [three-line patch](empty-known-sources.patch) returns null immediately after
scoped filtering leaves no candidates. It changes only that body. Removing those
exact three lines recovers the entire parent source byte-for-byte. All other
native sources and three of the four emitted class payloads remain byte-identical.
Legacy null-scoped behavior and actual native payment are unchanged.

## Executed Checks

- New **four synthetic native API checks**: parent two strict failures/two passes;
  corrected four passes, zero errors. Both seats include reject-all and legitimate
  source/legacy parity. The test sets explicit synthetic AI preference metadata
  on real native card abilities; it is not canonical Oracle text or a full game.
- The unchanged original **thirty native checks** also pass on the final build,
  including the six hidden-mana checks and actual owner-payment controls.
- Source, class and explicit input manifests verify. The builder preserves parent
  identity/inputs separately and records the current source/payload hashes.

Final content ID:
`ff89fd32da4e011d9e8f9af613a07a484894171ba7e4045c3932fcfaed4de398`.
The first guard build also passed, but its input-list bookkeeping was corrected
in a separate preserved stage; native source/class bytes did not change.

## Reproduce

```sh
bash tools/engine_evaluation/forge/native-ai/empty-source/build.sh \
  /absolute/qualified/BUILD-IDENTITY.json /absolute/fresh/local/candidate
bash tools/engine_evaluation/forge/native-ai/empty-source/test.sh \
  /absolute/qualified/BUILD-IDENTITY.json /absolute/fresh/local/candidate/shadow \
  /absolute/fresh/local/empty-checks
bash tools/engine_evaluation/forge/native-ai/known-mana/run-tests.sh \
  /absolute/qualified/BUILD-IDENTITY.json /absolute/fresh/local/candidate/shadow \
  /absolute/fresh/local/thirty-checks
```

Use [the current profile approval](profile-bundle.json) with the
[operator profile builder](../PROFILE.md). Application lifecycle, save compatibility
and broad fairness/strategy acceptance are separate. The original cost-profile
game remains historical; the final profile's first UI attempt failed on the old
frontend's rejection of a genuine anonymous cleanup input, not a native AI
exception. That failure is preserved rather than relabelled green.

After the separate parser correction on app source `8bee1327`, profile `1643f3fd`
completed a natural built-UI game (222 starts/returns, Control win turn 17).
A separate deliberate-pass UI prefix reached the real anonymous cleanup input,
clicked an offered card and verified hand eight to seven plus the same card in
graveyard, then explicitly closed without claiming a winner. See the
[final scope and evidence](../../../../../docs/testing/native-ai-knowledge-boundary.md).
No broad strategy/fairness or positive new-build cold-save claim follows.
