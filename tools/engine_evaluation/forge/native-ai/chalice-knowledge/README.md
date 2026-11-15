# Chalice Knowledge Policy: Controlled Native Family

Derived from Forge Team/Card-Forge revision
`61e9442c433711a82258daca3236f936a1d6f70e`, GPL-3.0-or-later; see LICENSE and
NOTICE. This is a derived correction, not a from-scratch AI implementation.

## Frozen Inputs and Observed Status

`source/forge-ai/src/main/java/forge/ai/ability/PermanentAi.java` is exactly
`5608d80db5a78f164dbdf582c13a887968fc52c7c0e5e628e66709dae7b26fc2`.
The full upstream preimage and zero-fuzz `PermanentAi.patch` are included.
`SOURCE-PRESERVATION.json` proves unchanged upstream method bytes outside the
approved Chalice branch, imports, helpers, and attribution header.

`NativeChalicePartitionAudit.java` is the byte-unchanged original (`730112...`).
`NativeChaliceGoldenAudit.java` is the frozen additional audit (`379e36...`).
Six full canonical programs are pinned against the native cardsfolder originals;
none is truncated or substituted into the live native card database. PINS.json
pins this family; ORIGIN.json and DECLARATION.json state provenance and scope.

Parent observed the exact candidate pass all 18 controlled contrasts, native
exit 0 in 12.9218 seconds. That was not an execution of this portable runner.
No public-runner result or app qualification is claimed here. Separate app
results are not part of this family's assertions. Parent review and one explicit
portable candidate qualification are still required before publication.

## Knowledge Contract and Limits

Starting registration is disclosed/authorized, including supplied non-Main
sections. Printed PaperCard/Rules values supply the histogram: split costs are
combined and DFC primary-face values are used. Existing MV-zero land/own-Chalice
exclusions, X affordability, phase rules, existing Chalices, and thresholds stay.

Only native public static-source zones are traversed. Both observer CardView
visibility guards precede live paper identity/abilities; Hand/Library are not
iterated. Unknown face-down removals remain possible candidates. Registered
non-Main copies reserve quantities before subtracting visible spent originals.
Native token/copy/LKI/clone/merge/collectible filters reject obvious ambiguity.
They are not a perfect started-in-main proof: extraCardsOnBattlefield,
non-section imports, and arbitrary producers changing flags are not globally
certified. Public conjured/copied threats are not added to the starting pool.

Known potential casting permissions retain eligibility without timing, payment,
generic validity, or canPlay probes. Native EffectZone/source activity and
AffectedZone bounds are respected; Library-only Future Sight does not retain a
Graveyard candidate. Conditions, card/player applicability, or AffectedDefined
that remain unresolved cause conservative retention within the known bounds.
The included graveyard-casting keywords include genuine Escape, not Unearth
alone. This is bounded potential-casting accounting, not all-card/alternate-face
forecasting; it adds no persistent knowledge framework.

## Cases and Privacy

The 18 first-choice cases are original eight plus ten additional cases, both
seats: opaque exile (four), spent Opt (two), returned known Opt (two), and real
Breach Escape (two). Original private pairs require identical public input/RNG
and action/X invariance. Telepathy controls require genuine visibility/input
contrast, not output divergence. The old standalone main is not rerun; its
unchanged firstChoice seam is reused by the frozen golden audit. No claim of
identical predecessor standalone-main execution history is made.

Poses are constructed, not natural games or paid setup histories. Only exact
native-selected actions execute; no X, cast, or winner is forced. Each fixture's
seed is declared before construction. There is no seed search or late RNG reset.
Hands, RNG, logs, full argv, and case records stay in fresh private evidence.
Only aggregate summaries are printed. Keep active evidence local; archive it
privately on verified NFS afterward, never execute a database there.

## Portable Gate

After explicit parent authorization, from any checkout location:

```sh
python3 run.py "$BASE_BUILD_IDENTITY_JSON" "$E4_PREFIX" "$FRESH_LOCAL_EVIDENCE" "$E5_CANDIDATE_PREFIX"
```

Prefixes are directories containing MANIFEST.json, source/, and shadow/.
Omitting the candidate selects baseline mode, whose genuine RED exit is preserved;
no new baseline run is requested or performed by packaging. No HEAD equality or
private scratch-root discovery is used.

The runner pins the exact qualified base identity/content manifest and verifies
all 59,971 listed native resources before/end. E4 must match the complete 8/15
manifest. Candidate must match the complete 9/16 manifest, preserving every E4
source/class and adding only PermanentAi source `5608...` / class `bb532...`.
Prefix inventories reject extra files. Physical pin checks and actually loaded
class origins are reported separately; no class/AI/cost calls force coverage.

Audit compilation and execution share a prospective 300-second budget, with
five-second forced-shutdown grace, 1500m heap and one processor. Each is contained
in bwrap with a private network/PID namespace, cleared environment, read-only
inputs and own writable scratch. Only one owned JVM runs at a time, with at most
one other JVM admitted. The runner preserves the native exit via SystemExit;
timeout, missing result, harness errors and changed pins are not passes.

This runner imports neither the app nor a database module. It does **not** install
the private JNI SQL-denial instrumentation or claim global native SQL denial.
Network namespace isolation is real; broader app/SQL safety is not inferred.

## Product Rebuild Command

The runner compiles only the two unchanged audits, never the product policy.
For an independent product build, derive JDK and BASE_CP from the supplied
BUILD-IDENTITY JSON, then compile into a fresh local directory (no shell tracing):

```sh
"$JDK/bin/javac" -J-Xmx1500m -J-XX:ActiveProcessorCount=1 --release 17 \
  -proc:none -implicit:none -sourcepath '' -cp "$E4_PREFIX/shadow:$BASE_CP" \
  -d "$FRESH_CLASSES" source/forge-ai/src/main/java/forge/ai/ability/PermanentAi.java
```

Expect exactly `forge/ai/ability/PermanentAi.class`, SHA-256
`bb532065e50b3ead54c2711bc73c9d6a2d18d37b5e67fc5fad61d28c7c15298d`.
Use the parent's reviewed builder to copy E4 unchanged into a fresh prefix, add
this one source/class, and compare every byte/inventory with CANDIDATE-PIN.json.
Do not merely copy that manifest onto an unverified payload. No builder, profile,
source installation, CI change, or gate is executed by this package preparation.
