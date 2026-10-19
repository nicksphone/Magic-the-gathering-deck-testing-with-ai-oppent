# Frozen 4eb Token Media Packaging Audit

Tests/report only, exact published `4ebcd5f` source archive SHA256
`05d5d42fb89efce8c7dd2c77ab6cfc51c78861b3ee1484de8236131bc71bd7f1`.
No later lazy-startup main/repository overlay is included. No production file,
existing test, tracked asset, API, schema, or metadata change was made.

## Actual Cold Evidence

The archive contains `card_data/assets/generic-token-creature.svg`, not an
ignored image cache or database. Its SHA256 is
`a3114095c760517186807f8753d109000174460a20ee72693ff9b9a69efc5e85`.
Current production code copies that tracked asset into the disposable image
cache when ensuring the fallback. The prior generic missing-asset behavior is
not reproduced on this source.

The unchanged standalone cold offline probe passed: absent DB, absent image
cache, 119 shipped names hydrated, 119 generated placeholders and the generic
SVG served through actual HTTP, zero network attempts, idempotent match start
and repository recovery. Hydration is not a 119-card execution certificate.
The five original token-image tests also passed from an independent initially
cache-empty/DB-absent extraction.

The authoritative suite started from a third exact extraction with no cache
and no database. All 11 complete selected modules ran serially under a
600-second bound: **87 PASS / 1 strict FAIL**, no errors/skips/xfails, 49.81s.
The first warm-root whole run gave the same result and is retained separately,
not mislabeled as cold qualification. Installed external dependencies were
read-only; no download, borrowed art, live service, or NFS SQLite execution.

The five new packaging contracts passed within the whole suite. Actual paid
Blade Splicer HTTP casts on both seats create the canonical colorless 3/3
Phyrexian Golem artifact-creature token. First strike is an effective grant
from Blade Splicer, not a fabricated intrinsic token keyword. Durable recovery
preserves the token; its image GET returns the tracked SVG byte-for-byte and
does not alter memory/controller/SQLite snapshots. Generic fallback art is not
claimed canonical token illustration art.

## Remaining Findings

The single strict suite failure is the existing
`test_card_image_sync.py::test_sync_card_by_name_merges_fallback_text_for_blank_cached_card`.
It invokes explicit `sync_card_by_name` without a transport stub and attempts
network access on a clean checkout. The guard blocks the connection before it
occurs. This is not evidence of gameplay or startup performing remote sync;
those dedicated cold paths have zero attempts.

Separately, the original test function and all its assertions pass unchanged
with `get_with_backoff` explicitly raising `httpx.ConnectError`; no socket or
SQLite attempt occurs. Minimal TEST-ONLY proposal: make the existing explicit
sync test's unavailable-network transport deterministic with that stub. Do not
create an ignored cached PNG to bypass the sync path or alter product exception
handling to hide a forbidden connection. The whole unmodified suite remains
87/1; the separate transport experiment is not a green whole-suite claim.

The tracked fallback is installed at `main` IMPORT, before SQLite creation.
`TestClient` without lifespan can serve it while the DB remains absent.
Entering lifespan initializes synthetic SQLite and seeds/restores repository
state. Lifespan is not what reinstalls the generic image.

A separate controlled runtime-eviction observation deletes ONLY the generated
cache copy after import and memoizes the token URI. Lifespan/health still work,
but that URI is 404 and a memoized lookup does not reinstall it. This is not a
cold-package missing asset: it is a cache-lifecycle limitation. The audit records
404 explicitly rather than manually replacing ignored art to fake success.
No production repair is implemented or claimed.

## Scope And Integrity

All 1,550 original non-graph source files are byte-identical in all three roots.
Only two NEW test/probe files and this NEW document are proposed. Full existing
canonical fixtures/provenance are reused without Oracle, type, cost, or name
rewrites. Source manifests, initial cache/DB records, guarded commands, terminal
JUnit/logs, media hashes, cold subprocess traces, and separate transport evidence
are archived. Draft failures from the incorrect intrinsic-first-strike test
assumption are retained and not claimed engine defects. Original assertions
were not weakened; only the new test draft was corrected to the real printed
and effective distinction.

The archive is operational audit evidence, not a full-suite, fresh dependency
installation, browser, complete rules, or live deployment certificate. The prior
global-keyword 298 package remains immutable and is not overlaid here.
