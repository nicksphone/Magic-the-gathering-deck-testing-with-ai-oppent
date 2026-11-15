# Ready-Board Multicolor Regression

These six JSON files are complete, byte-preserved Scryfall named-API response
bodies. `PROVENANCE.json` records each public request URL, SHA-256, Oracle and
printing IDs, UTC intake metadata, HTTP status, and allowlisted public headers.
No requests occur during tests. The intake UTC value was recorded after the
batch; each HTTP Date retains its individual server-response timestamp.

`tests/test_ready_mana_multicolor.py` loads fixtures relative to its own file,
checks their hashes, and imports the actual `ai.mana_resource_policy`. It has no
phase switch, environment requirement, external helper, or filesystem output.
From `backend`, run the complete two-seat module with the project's Python:

```sh
python -m pytest -q tests/test_ready_mana_multicolor.py
```

The existing battlefield is Hallowed Fountain plus Mountain. The selected
tapped land is Azorius Guildgate; the alternative is Savage Lands. Held spells
are Azorius First-Wing (`{W}{U}`) and Duress (`{B}`). Current exact payments are
all false. Ready-board payments are `[true, false]` with Guildgate and
`[false, true]` with Savage Lands. Independent single-color capacities cannot
prove retention of the mixed-color payment.

Both seats must preserve Guildgate. Native checked actions pay 2 for First-Wing
with Guildgate, reject First-Wing with Savage Lands, and pay 1 for Duress with
Savage Lands. Root, global/state RNG, agent and supplied-action purity checks
remain in the test. Probe spies forward to native functions without replacing
their results. The profile requires 8 exact plus 48 capacity probes; the four
unchanged native land-admission checks are counted separately. Budget 55 must
abstain before probing; budget 56 must execute the full nonregressive profile.
