# November 8 release cache and native-zero fixtures

The release-card tests now use complete pinned official inputs for both cached
DFCs and the Forest stock. The numeric-zero case uses Jace's genuine 0/2 front;
the HTTP transform case retains Cathar and its 3/3 Moonrage Brute reverse face.
An added assertion checks zero in the public native card view after snapshot
restoration. This changes fixture data and acceptance coverage, not production
hydration, face selection or rendering code.

## Data and original contracts

The finite helper in `tests/release_printed_fixture.py` admits only the two
named parents and returns a fresh complete production-normalizer cache
projection. Jace reuses its 61-field pinned parent including retained provenance;
Cathar reuses its 63-field seed155 parent. The zero test converts the correct
printed 0/2 scalar strings to integers at the cache interface, retaining the
original integer-zero assertion without inventing a printed fact. Display uses
a fixture-only URI; no art is downloaded.

The Forest input reuses the existing complete direct Factory entry. All 62
original assertion ASTs across the release module and its two fidelity consumers
remain unchanged. The original names, parameters, quantities and seeds remain;
one public/base-power zero assertion is added. The existing Anthem function,
Bears/Goyf fixtures, deliberate unknown-stat vector and token-asset check remain.
RAW objects, provenance, shared loaders, normalizer and production code are
unchanged.

## Observed results

Three private setup observations fail on the old input rows and pass on the
canonical rows. They stop before hydration, HTTP or Factory consumers and do
not count as original-test or HTTP qualification.

A separate observation executes the original zero caller, including its
original assertions and snapshot round trip. The old cache's fake zero coexists
with a printed 2/2 face: the public power, base power, native power and retained
physical power are all 2. The old test therefore did not exercise native zero.
The unchanged candidate facts yield four actual zero values and printed `"0"`;
the original test now explicitly guards the public/base-power result.

The final stronger source passes one combined command over all three whole
modules, with zero failures, errors or skips:

| Whole module | Ordinary passes |
| --- | ---: |
| `test_release_card_contracts.py` | 5 |
| `test_release_printed_fidelity.py` | 2 |
| `test_event_release_canonical_T57_fidelity.py` | 15 |
| Combined execution | 22 |

JUnit time is 2.071 seconds, guarded runner time 2.373 seconds and supervisor
time 4.001 seconds, with two existing deprecation warnings. An earlier 22-pass
epoch precedes the new public-zero assertion and is retained separately;
the overlapping executions are not added together. The final native observation
also passes independently, with the actual public/native/retained zero values.

## Source, IO and retained setup failures

The base is `d6ef0a868aa751cc73bf415f0656920cac6cb80b`. Three frozen epochs each
contain 5,132 public regular files. The final working overlay contains only the
two test/helper files and its plan ledger. SHA-256 and recorded Git blob IDs,
versioned harnesses, RAW pins, complete JUnit identities and normal process-group
closure verify. Jace file SHA-256 remains
`181985b1b21e065f153502df37dbea3654bf163b0b4030af30d4aac8779e134c`;
seed155 remains
`194abe0a2d6e1bb6139d0f569a347e419c75bd9349091f583cf79fa6a6036732`.

SQL, children, external networking and OpenAI imports are denied before
collection. The whole-module run admits UNIX socket construction for ASGI and
uses the previously qualified 10ms test-loop timer: two loops, four socket
constructions and fifteen timer ticks. It makes zero SQL connections and zero
observed AI choices. There is no autoplay or natural game. This is adjusted
ASGI/fixture evidence, not browser, TCP, native Forge, persistence or hosted CI.

Content opens for writing are restricted to the owned execution directory and
its source copy's generated SVG cache. Capture/logging files and the small owned
asset/placeholder cache are accounted for; the cache is not globally cold.
This is a content-open bound, not a general filesystem or adversarial sandbox.
Sixteen exercised controls cover SQL constructors, network/process operations,
protected-name synthetic fixtures, provider import and foreign content writes;
positive UNIX sockets close with unchanged FD metadata.

Two harness setup failures remain: pytest capture initially selected a default
temporary directory outside the declared root, and its logging handler then
selected `/dev/null`. Both stop before application collection. Explicit owned
temporary and log paths fix setup without relaxing the guard. Original versions
remain hash-bound; the current audit/write predicate ASTs are identical to the
exercised controls. All eight execution groups close normally, including those
failed setups. No real protected artifact or user database is read.

A final metadata/source auditor verifies these boundaries without runtime IO.
Independent final review approves the bounded correction without findings.
Private evidence remains under
`/home/nick/mtg-rc-evidence-20261108/release-canonical-cache`. This finite positive
fixture correction leaves remaining Task 1.3 inputs, Phase 1, full current-source
backend/hosted checks, AI quality and all RC gates open. It does not certify
Jace's complete ability behavior or gameplay strength.
