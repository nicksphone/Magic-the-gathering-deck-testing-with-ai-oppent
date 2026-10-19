# Spell-Type Caller Projection

The follow-up over `b7067d70` changes only three query call sites in
`restrictions.py` and `costs.py`, plus their two `CARD_TYPES` imports. Each caller
projects the actual effective, selected-method view onto the existing card-type
domain before calling `spell_cast_prohibited`. No query, parser, fixture, Oracle,
payment, face-selection, browser assertion or deadline is changed.

## Observed Regression

The full browser run on `b7067d70` stops at
`browser-human-actions.mjs:345`, waiting for the offered Tamiyo cast. The original
fixture represents its hand card as `Legendary` plus `Planeswalker`. The strict
typed query correctly rejects a tuple containing a supertype; the callers were
passing that tuple without projecting its domain. The actual UI reports a
battlefield casting prohibition despite that fixture having no battlefield
sources. Later recovery, natural BO3, interactive and Cathar programs are
unreached in this run, not failed gameplay or completed acceptance.

The new regression executes the whole unchanged fixture function with only its
publication boundary captured. All three caller surfaces reproduce the error.
The same tests retain strict direct-query rejection, cache/root purity and
empty-type rejection. Selected casting-method views are still evaluated before
projection; there is no default-face or name-based fallback.

## Focused Evidence

The same 34 new cases reproduce 13 failures before the correction and pass
afterward. Twelve real canonical Tamiyo cases cover both seats and all three
hybrid branches, under factory and printed-supertype representations. Actual
checked payment, stack publication, life totals and entry loyalty are compared.
The full canonical Oracle and raw fixture bytes remain unchanged.

The complete seven-module focused cohort passes all 254 cases in 109.97 seconds,
with all original 102 Jailer cases retained. Source and cached dependencies remain
byte-equal. SQL, sockets, children and provider/chooser execution are denied
before imports; these are in-memory mechanics, not HTTP/browser qualification.

Its first attempt also passed all 254 tests but failed the wrapper because the
real token path created one generated SVG in the source cache. That ledger is
preserved. The qualified repeat uses only execution-time media-cache bindings
to a fresh owned evidence directory, before hashing and collection. The SVG
equals the shipped asset; no helper, test, content rule or source file is mocked
or changed for this correction.

## Remaining Acceptance

The independent 34-whole-module native cohort appends these 34 cases to the exact
original 781-case prefix. It completes 805 ordinary passes and ten original
opt-in skips in 87.59 seconds, exit zero. XML independently verifies all 815
ordered cases, all 34 new passes, and no failures/errors. All 2,931 source and
2,021 cached dependency files remain byte-equal. A fresh execution-only media
cache is outside source; no developer cache files are copied into this gate.

The same backup-call-only diagnostic observer records 24 normal original calls
and 101 actual progress callbacks. The largest measured whole call is
0.151618126 seconds. Arguments, results, exceptions and the original five-second
deadline remain unchanged; observation overhead is not asserted to be zero.
The original function and profiler are restored before disposal. Jobs, threads
and external-I/O denials are absent, and external scans of all 25 actual closed
database paths are empty. This does not explain the earlier backup timeout.

The ten opt-in child HTTP cases require a separate native gate and must not be
counted as ordinary passes. Full current browser,
protected backend CI, clean-machine/deployment and the original Gates 1--3
remain open until their own evidence is complete. AI quality labels and budget
counters have not been reset or promoted by these component checks.

## Pins

Restrictions: `3be8f42b6c20352cb76f973351c5c09e3a913c08f8ae58f728168804030b9ddc`.
Costs: `9294bde1dc08d5cf78df988ae7efeea53ab20d0e65152c94b855a428fb0cca6c`.
Unchanged query: `a2da0e1705ff87b9bac9c3ef367b7466c99210340d247cecd5546e672f51fd16`.
Focused patch: `148e428ac15aa35d56719c669062353004787919e293599fd373cf4d518472fc`.
Private logs, databases, browser traces and benchmark inputs remain archived
outside the public source tree.
