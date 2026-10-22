"""Parent-invoked installer bootstrap from the separately hash-pinned pip wheel."""
from pathlib import Path
import runpy
import sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'wheels/pip-26.2.1-py3-none-any.whl'))
sys.argv = [str(root / 'admin/pip_offline.py'), str(root / 'evidence/INSTALLER_IO.json'),
            '--isolated', '--disable-pip-version-check', '--no-cache-dir', 'install',
            '--no-index', '--find-links', str(root / 'wheels'), '--require-hashes',
            '--only-binary=:all:', '--no-compile', '--report', str(root / 'evidence/INSTALLER_REPORT.json'),
            '-r', str(root / 'inputs/installer.lock')]
runpy.run_path(str(root / 'admin/pip_offline.py'), run_name='__main__')
