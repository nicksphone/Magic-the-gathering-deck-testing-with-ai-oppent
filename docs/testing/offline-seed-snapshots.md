# Offline Seed Snapshot Isolation

Offline metadata lookups now return caller-owned dictionaries, including nested
faces and color arrays. Previously, clearing a returned seed row or editing a
hydrated face changed the shared in-memory canonical catalog. Later lookups,
hydration calls and real Python MatchFactory births could inherit those edits.

Both ordinary normalized lookups and the historical `//` front-name fallback
deep-copy the complete stored payload. Name normalization, missing-name results,
seed values, cached/knowledge precedence, rules and AI policy are unchanged.
The front-name convenience does not certify an arbitrary supplied back face as
a real or supported card. Direct mutation of the exported internal catalog and
general aliasing between gameplay structures are outside this correction.

## Regression And Integration Evidence

The initial eleven new cases ran on unchanged code: ten failed and one passed.
They expose root/nested mutations, aliases, repeated hydration, both-seat actual
Python MatchFactory births and snapshot restoration. Tests restore the faulty
baseline's in-memory catalog after each case; no seed file is rewritten.

Review found the real Delver combined name exercises the direct index rather
than the front fallback. Two explicit historical-lookup mutation cases were
added. Restoring only the old fallback return in memory makes precisely those
two fail while the other eleven pass. The final isolation module has thirteen
cases. Sentinel caller edits are deliberately malformed metadata operations,
not fabricated Oracle used as a gameplay fixture.

The full final declaration passes **562 cases in eleven whole modules**, zero
failures/errors/skips, in 19.03 seconds. A pre-import Python audit hook denies
SQL, socket and child-process events and records zero denials. Declared product,
test and seed hashes stay equal before/after execution. The declaration includes
the isolation, hydration, cache-container/type, canonical fixture, face-color,
mana-source, 155-row migration and startup-media-generator modules. Raw logs and
the exact module list remain private in
`/home/nick/mtg-rc-evidence-20261108/seed-hydration-final-cohort.*`.

The ten whole current-source-binding unittest methods separately pass. These
are source/metadata controls, not additional gameplay cases or a summed cohort.
Independent follow-up review approved the correction with no remaining findings
and separately reran 385 cases across the complete isolation, seed migration and
startup generator modules. Those modules overlap the 562-case declaration.
The review's earlier filesystem-audit harness setup failures were retained;
they required no product changes.

## Startup Generator Compatibility

Independent review identified a real consumer regression: the startup generator
first rejected the changed seed source digest, and repinning that file alone
then failed its old object-identity check. Both failures were reproduced and
preserved. The generator now compares complete typed structural JSON facts;
the exact reviewed seed source pin is updated without any wildcard admission.
Added fault controls retain rejection of wrong text, missing fields and a bool
replaced by its numerically equal integer. All pre-existing assertions remain.

The whole generator module passes 203 cases. It is included in, not added to,
the 562-case declaration. A separate old/new artifact comparison executes both
actual generators on their finite public input sets. All 164 media entries and
all seed/deck structural facts are identical. Only the seed-module source pin
changes from `cb64ae85690d5239a24895b4ed6ac8a46b5f4c15de64d5bb67192eb187b72c71`
to `ddd392f11ea66ccc440ba5b5d551576df1feb903025e8c80f116dd5c6ac121c5`.

The complete 155-card seed file retains SHA-256
`9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037`.

## Matched Production-Python Game Component

A separately declared two-execution comparison uses the shipped Tempo and Tribal
decks, one fresh fixed coordinate, Master difficulty and the unchanged resource
limits. Both decks pass the existing offline readiness/unsupported-mechanic checks.
Only the seed API differs: the baseline executes its exact old implementation
before importing consumers; the candidate uses caller-owned snapshots. All other
declared source files, deck facts, registration order and seed are identical.

Both games complete naturally: Tribal wins at turn 12 after 346 checked actions.
All 808 raw log lines, including all 346 action traces, are exactly equal; the
normalized logs and hashes also match. Independent reading verifies both raw
evidence receipts, zero SQL/socket/process denials, bounded results, unchanged
source pins and reaped child processes. Neither execution is retried or replaced.

These are two implementations at one same-seat coordinate, not two independent
strength samples or a seat-balanced matrix. They do not prove general semantic
neutrality, exact final state/RNG streams, BO3, HTTP/browser behavior or native
Forge acceptance. Raw games, hands, seeds and stage traces remain private under
`/home/nick/mtg-rc-evidence-20261108/seed-game-comparison/`.

No runtime/operator artifact was installed, no user database was read, and these
components establish no HTTP/browser/native Forge or full release gate.
Hosted qualification remains pending because connector mutations require
approval unavailable under this session's `never` policy.
