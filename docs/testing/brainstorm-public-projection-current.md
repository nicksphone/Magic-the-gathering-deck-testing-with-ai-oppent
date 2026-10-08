# Brainstorm Public Choice Projection

The current integration adds only the `hand_top_order` public projection in
`rules_engine.optional_reveal.public_choice`. Public choices retain their
kind, player, options, counts, labels and optional type-line metadata. Internal
resolution frames and continuation state remain in the authoritative pending
choice and snapshots, but are not exported as display metadata.

Frozen qualification: `parent-integration/brainstorm-postfix20-qualified-s8MZsS/`
under the MTG NFS artifact directory. Its corrected whole 20-case gate passed
in 51.75 seconds, with 20 completed application lifespans and verified database,
thread, worker and descriptor closure. Its source was the frozen Stage1
baseline plus this exact projection, not the entire current release union.
The original 16-pass/4-fail diagnostic remains archived separately.

Production preimage: `5ff7a198ef7d62a03608ea28e5ffcfbfa52d17c820fc91f29b8544248068f837`.
Postimage: `3a6ca78e28f980a6d40d11d4468c5cf0ca69b3d0ef13f8074ca6e8587a1ef92b`.
Both new test modules are copied byte-for-byte from that qualified packet.

The integrated current-source pure module independently passed all 11 cases
in 3.78 seconds with native SQLite, socket and child-process denials installed
before pytest. Production, test and existing local database hashes were equal
before and after; descriptor maps matched and no extra threads remained.
The first parent harness stopped before collection because its evidence path
was outside the declared guard directory. Only that harness evidence binding
was corrected; application and regression bytes were unchanged.

Run the pure regression with the existing helper on the import path:

```bash
PYTHONPATH=backend:audit/brainstorm python -m pytest -q backend/tests/test_brainstorm_public_projection_goldens.py
```

The HTTP regression additionally requires a reviewed isolated local database
and completed application-lifecycle closure. Neither component result proves
the final current-source browser, AI-strength or full-release gates.
