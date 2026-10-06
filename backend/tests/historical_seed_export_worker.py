"""Run the actual exporter CLI against the explicit historical119 test cohort."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
from scripts import export_builtin_oracle_seed as exporter


def main():
    for option in ('--database', '--output', '--fact-ledger', '--preservation-seed'):
        if option not in sys.argv:
            raise SystemExit('Fixture CLI requires explicit isolated paths: ' + option)
    seed = Path(__file__).parent / 'fixtures/mh3_seed_gap/seed119_before.json'
    ledger = json.loads((Path(exporter.__file__).parents[1] / 'card_data/mh3_catalog_seed_provenance.json').read_text())
    assert hashlib.sha256(seed.read_bytes()).hexdigest() == ledger['baseline_seed_sha256']
    qualified = json.loads(seed.read_text())
    assert len(qualified['cards']) == 119
    exporter.shipped_names = lambda: set(qualified['cards'])
    exporter.DEFAULT_SEED = seed
    exporter.main()


if __name__ == '__main__':
    main()
