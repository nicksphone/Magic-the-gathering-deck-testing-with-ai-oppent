# Historical Catalog and Seed Fixture Transitions

Current base: exact5d0adb29fc51400f6237704e8d3752af2ce370a0 plus frozen catalog
and append36 canonical seed increments. No moving source or user DB changes.

The unchanged 119-only exporter fixtures failed24 cases before and after the
seed append because shipped_names covers155 catalog names. Exact current
unadapted baseline reproduced26 failures: those24 plus two obsolete Nadu-absence
assertions. Preserve all original logs and the old source artifacts.

Exporter tests now bind their explicit119 cohort and qualified119 seed snapshot
rather than implicitly reading the production155 inventory. Both direct calls
and subprocess CLI invoke the real unchanged exporter; a test-only CLI harness
binds the same fixture cohort. Every original golden/atomic-negative assertion,
119-card output and16-face/17-fact ledger remains unchanged. The worker refuses
implicit database/output/ledger/preservation paths. No production exporter flags,
code, parsing, preservation relaxation or automatic155 regeneration is added.

The historical Nadu witness now asserts exact full canonical row equality plus
genuine scryfall_id alias. Adventure colors/source priority/engine-certification
checks remain unchanged. NEW append tests separately prove all155 names, exact36
raws and all119 prior properties. The global seed coverage assertion is untouched.

Metadata readiness and historical format provenance are not current legality,
full-Oracle execution, gameplay strength or learned card-quality certificates.
The existing exporter still needs separately scoped full-raw preservation before
production155 regeneration; this fixture qualification is not that certificate.
