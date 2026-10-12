"""Helpers for the pod tests: run lib.sh functions in bash against temporary directories."""
import os
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
POD_DIR = ROOT / 'docker' / 'pod'
LIB = POD_DIR / 'lib.sh'


def pod_file(name):
    return (POD_DIR / name).read_text(encoding='utf-8')


def pod_code(name):
    """A pod file without its comment lines."""
    return '\n'.join(line for line in pod_file(name).splitlines() if not line.lstrip().startswith(('#', ';')))


def run_bash(script, env=None, check=True, timeout=30):
    """Run bash code with lib.sh sourced under `set -u`, in a minimal environment."""
    full_env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', **(env or {})}
    return subprocess.run(
        ['bash', '-c', f'set -u; source "{LIB}"; {script}'],
        env=full_env, capture_output=True, text=True, timeout=timeout, check=check,
    )


class PodLayout:
    """Temporary stand-ins for the container disk (PGDATA, state dir) and the network volume."""

    def __init__(self, root: Path):
        self.root = root
        self.volume = root / 'volume'
        self.backup = self.volume / 'gateway-backup'
        self.pgdata = root / 'pgdata'
        self.state = root / 'state'
        for path in (self.backup / 'base', self.backup / 'wal', self.backup / 'dumps', self.state):
            path.mkdir(parents=True)

    def env(self, **extra):
        return {
            'VOLUME_MOUNT': str(self.volume), 'BACKUP_DIR': str(self.backup),
            'PGDATA': str(self.pgdata), 'POD_STATE_DIR': str(self.state), **extra,
        }

    def init_cluster(self):
        self.pgdata.mkdir()
        (self.pgdata / 'PG_VERSION').write_text('17\n')

    def add_backup(self, stamp, start_wal='000000010000000000000002', complete=True):
        folder = self.backup / 'base' / stamp
        folder.mkdir()
        if complete:
            (folder / 'COMPLETE').write_text(start_wal + '\n')
        return folder

    def add_wal(self, name, content=b'wal'):
        path = self.backup / 'wal' / name
        path.write_bytes(content)
        return path

    def set_owner(self, pod_id):
        (self.backup / 'OWNER').write_text(pod_id + '\n')


class PodTestCase(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pod = PodLayout(Path(tmp.name))

    def lib(self, script, check=True, **env):
        return run_bash(script, env=self.pod.env(**env), check=check)
