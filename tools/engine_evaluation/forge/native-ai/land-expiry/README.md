# Native Expiring-Land Preference

This reuses the Forge Team/Card-Forge contributors' rules, card programs and
baseline AI under GPL-3.0-or-later. Their authorship is retained in the source
patch, NOTICE and LICENSE; see the repository THIRD-PARTY-NOTICES.md.

The one-source patch changes only the native fallback when land scores tie.
Scores are still computed once and unchanged. Known expiring exile access wins
the tie; original order remains when neither or both alternatives are urgent.
Existing combo selection, LandPlanner, earlier returns and native legality are
unchanged. Unknown, persistent and other-duration grants fall through normally.
This is not a complete land planner or a universal strategic-equivalence claim.

Apply `land-expiry.patch` only over the exact qualified parent in SOURCE-PINS.json,
on a fresh copy. The resulting prefix has thirteen sources/twenty-one classes;
one source and its two emitted classes differ. PAYLOAD.json binds the complete
closure. Existing runtime_profile.py composes the isolated profile after a real
rebuild with the qualified Forge dependencies; this package is not a standalone
installer and does not switch a live profile.

## Evidence

- Unchanged NativeExpiringLand6: two actual paid Iteration source-choice REDs
  become ordinary AI-selected, natively played exile lands. Four expired/used-drop
  controls stay passing. Initial fixture mistakes are preserved privately.
- NativeExpiringPermissionProtocol17: one native paid frontier, then seventeen
  explicitly labelled helper/metadata checks. Six hidden-body read guards and
  persistent/unknown alternatives pass. Spy cases are not real cards or games.
- Existing pressure70, knowledge38 and boundary48 pass; unchanged gain response6
  and preservation10 also pass. These are separate controlled cohorts, not games.
- Four fresh Tempo/Ramp games complete cleanly. The original natural case now
  plays exile Island16 and retains hand Island24. No win-rate improvement is
  claimed; the historical comparison also predates the separate gain-denial fix.

Both Java mains take one fresh output-directory argument. They require the
existing guarded native harness and classpath. The protocol source additionally
uses Mockito with the existing pinned Byte Buddy agent enabled at JVM startup;
no dynamic-attach permission is needed. Do not infer runtime safety from source
checksums or launch an unguarded game to work around a harness failure.

For artifact bytes only, from this directory:

```bash
sha256sum -c SHA256SUMS
```

See [measured qualification and limits](../../../../../docs/testing/native-expiring-land-ai.md).
