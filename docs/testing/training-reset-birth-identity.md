# Training Reset Captures Its Final Identity At Birth

`TrainingEnvironment.reset` previously called the real `MatchFactory`, which
initialized nonempty private sideboarding facts with its generated UUID, then
changed only `state.id` to the deterministic provenance digest. Snapshot
validation correctly rejected the stale identity. This is a production-producer
conflict, not a reason to clear facts or weaken the snapshot validator.

The Factory now accepts optional keyword-only `game_id`. `None` retains UUID4
at the original birth point; supplied IDs must be plain, nonempty strings with
no whitespace or nonprintable characters. Invalid IDs reject before allocation
or capture. Training passes its existing provenance digest before construction,
and no longer assigns an ID after capture. Stock, card IDs, seed/RNG, metadata,
draws, facts schema, provenance and default positional arguments are unchanged.
The argument is internal construction context, not a new HTTP request field or
an authorization proof. Original deterministic snapshot assertions remain.

## Qualification And Boundaries

At immutable `2b9f3a601edfb17c2fbd8c1d5894c4a58b982683`, whole original training
module plus NEW6 collected56: 53FAIL/3PASS, 13.98s (original50=48F/2P,
NEW6=5F/1P). Additional pre-fix NEW19 API controls produced18F/1P, 2.39s.
The original RED packet and all failed ledgers remain immutable.

The final fresh five-whole-module gate passes602 ordinary cases, 120.88s,
zero failures/errors/skips. It includes original training50, NEW19, original
facts13/events8 and the whole actor-prevalidation512. Native SQLite aliases,
socket aliases and process operations were fenced before project imports,
with five native canaries plus two source-write canaries denied and no
unexpected operations. No application service, SQL or native AI chooser ran.
Genuine media producers wrote four files to empty owned scratch, not source;
all1950 source files, including the declared isolation marker, match before/end.

An independent parent checkout of the same correction passes the identical five
whole modules: 602 ordinary passes, 2 warnings, 129.66s, exit zero, with no
failures, errors or skips. Its full 3,205-file source map matches before/end;
all seven denial canaries pass, unexpected operations are empty, no database is
created, and the four genuine media files remain in owned scratch. This is a
separate qualification, not a sum with the author's cohort or the active native
measurement on the earlier source.

Two earlier five-module attempts are not relabeled as final qualification.
First:88P/2F/512E, missing owned marker and NEW native-vs-JSON comparison error;
second:602P with generated SVGs incorrectly placed in source. The NEW test now
compares the complete JSON wire domain; no old assertion was edited. The final
harness rebinds only real media globals/index to owned scratch and denies source
writes; it does not stub or preseed media, weaken I/O or prune tests.

The immutable-base static inventory found671 direct Factory calls in254 files;
the earlier staged inventory counted673 in255 because it included NEW6 tests.
This inventory excludes dynamic aliases. Existing five positional parameters
remain; only the training production caller adds the new keyword.
This is bounded in-memory rules/serialization qualification, not a native
benchmark, full hosted CI, arbitrary-card certification or measured AI strength.
