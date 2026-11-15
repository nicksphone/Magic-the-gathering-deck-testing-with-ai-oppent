# Pending Life-Gain Denial Source Delta

This reuses the Forge Team/Card-Forge contributors' card programs, rules and AI
under GPL-3.0-or-later. See [NOTICE](NOTICE), [LICENSE](LICENSE) and the attribution
in the patch and unchanged Java fixtures. The new policy is effect-typed, not a
card-name exception.

`gain-denial.patch` modifies only `DamageAiBase` and `DamageDealAi`. Apply it to
the exact parent prefix named in `SOURCE-PINS.json`, not a pristine Forge tree
or an arbitrary current checkout. Work on a fresh copy; do not overwrite an
active runtime or reuse old save IDs. `SOURCE-PINS.json` records the two source
pre/postimages and the qualified compiled postimages. The complete prefix remains
thirteen sources/twenty-one classes; the other eleven sources/nineteen classes
are unchanged.

The source-only package is not a standalone native-runtime installer. Rebuilding
and executing its Java mains requires the existing qualified Forge dependencies,
parent payload, classpath and isolated native harness. The profile composition
tool is the existing [runtime_profile.py](../runtime_profile.py). Do not run an
unisolated Java command or infer a live profile switch from these source files.
The private operator evidence retains the exact guarded command vectors and
before/after byte checks; no private trace is published here.

## Fixtures

- `NativeSkullcrackResponse6`: two funded pending-gain responses, two unfunded
  refusals and two explicitly observational no-pending cases. First selection is
  the ordinary Default AI callback. Manual rules controls are never AI successes.
- `NativeSkullcrackPreservation10`: own gain, already-blocked gain, harmful gain
  and opposing hexproof refusals, plus two ordinary AI-paid lethal wins.
- `canonical/`: six complete unchanged Forge programs, bound in
  `CANONICAL-PINS.json`.

Both sources run with one fresh output-directory argument and emit private
`summary.private.json`. Their sources are unchanged between baseline and
candidate. Original failing outcomes remain in the private evidence archives.

For a read-only artifact-integrity check without Forge, Java or a database:

```bash
python3 -B tools/engine_evaluation/forge/native-ai/gain-denial/selfcheck.py
```

This checks package bytes and declarations only, not gameplay or rebuildability.

See [qualification and remaining limits](../../../../../docs/testing/native-gain-denial.md).
