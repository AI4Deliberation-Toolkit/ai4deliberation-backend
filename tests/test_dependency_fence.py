"""Keeps the gateway thin: no ML/NLP imports may creep back into this repo."""
import ast
import os
import re
import tempfile
from pathlib import Path

from django.core.management import get_commands
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent

# Top-level module names that belong to the old NLP stack (now in ai4d-topic-toolkit).
BANNED_IMPORTS = {
    'accelerate', 'bertopic', 'fastapi', 'hdbscan', 'huggingface_hub', 'langdetect',
    'numpy', 'openpyxl', 'pandas', 'pyarrow', 'sentence_transformers', 'sentencepiece',
    'sklearn', 'tensorflow', 'tf_keras', 'torch', 'torchaudio', 'torchvision',
    'transformers', 'umap', 'xlrd',
}

# Distribution names (requirements.txt spelling) of the old NLP stack.
BANNED_REQUIREMENTS = {
    'accelerate', 'bertopic', 'fastapi', 'hdbscan', 'huggingface-hub', 'langdetect',
    'numpy', 'openpyxl', 'pandas', 'pyarrow', 'scikit-learn', 'sentence-transformers',
    'sentencepiece', 'tensorflow', 'tensorflow-cpu', 'tf-keras', 'torch', 'torchaudio',
    'torchvision', 'transformers', 'umap-learn', 'xlrd',
}

# Gitignored, local-only top-level folders that may hold old experiment code.
SKIPPED_DIRS = {'docs', 'resources', 'scripts', 'staticfiles', 'media', 'venv', 'env', 'myenv', 'ENV', 'node_modules'}


def _project_python_files(root=ROOT):
    for dirpath, dirnames, filenames in os.walk(root):
        top_level = Path(dirpath) == Path(root)
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith('.') and not (top_level and d in SKIPPED_DIRS)
        ]
        for name in filenames:
            if name.endswith('.py'):
                yield Path(dirpath) / name


def _requirement_names(text):
    for line in text.splitlines():
        line = re.sub(r'(?:^|\s)#.*', '', line).strip()
        if not line:
            continue
        egg = re.search(r'[#&]egg=([^&\s]+)', line)
        if egg:
            name = egg.group(1)
        elif line.startswith('-'):
            continue
        else:
            name = re.split(r'[<>=!~\[;@\s]', line, maxsplit=1)[0]
        yield re.sub(r'[-_.]+', '-', name).lower()


def _management_commands(script):
    return re.findall(r'(?:manage\.py|django-admin|-m\s+django)\s+([a-z_]+)', script)


def _imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module


class DependencyFenceTests(SimpleTestCase):
    def test_no_ml_imports(self):
        offenders = []
        for path in _project_python_files():
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            for lineno, module in _imported_modules(tree):
                if module.split('.')[0] in BANNED_IMPORTS:
                    offenders.append(f'{path.relative_to(ROOT)}:{lineno} imports {module}')
        self.assertEqual(offenders, [], 'ML imports found:\n' + '\n'.join(offenders))

    def test_requirements_have_no_ml_packages(self):
        names = set(_requirement_names((ROOT / 'requirements.txt').read_text(encoding='utf-8')))
        self.assertEqual(sorted(names & BANNED_REQUIREMENTS), [])

    def test_entrypoint_only_calls_existing_commands(self):
        script = (ROOT / 'docker' / 'web' / 'entrypoint.sh').read_text(encoding='utf-8')
        called = _management_commands(script)
        self.assertTrue(called, 'entrypoint no longer calls any management commands')
        unknown = sorted(set(called) - set(get_commands()))
        self.assertEqual(unknown, [], f'entrypoint calls unknown management commands: {unknown}')

    def test_requirement_name_parsing(self):
        sample = """\
scikit_learn==1.6.1
Huggingface_Hub>=0.2
sentence.transformers
-e git+https://example.com/x.git#egg=transformers
-e git+https://example.com/y.git#subdirectory=py&egg=hdbscan
torch @ https://example.com/torch.whl
django==5.2.8  # inline comment
# a full-line comment
--index-url https://example.com/simple

"""
        self.assertEqual(
            set(_requirement_names(sample)),
            {'scikit-learn', 'huggingface-hub', 'sentence-transformers', 'transformers', 'hdbscan', 'torch', 'django'},
        )

    def test_fence_skips_local_dirs_only_at_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ('scripts/top.py', '.hidden/h.py', 'pkg/scripts/nested.py', 'pkg/mod.py'):
                f = root / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text('')
            found = {Path(p).relative_to(root).as_posix() for p in _project_python_files(root)}
        self.assertEqual(found, {'pkg/scripts/nested.py', 'pkg/mod.py'})

    def test_management_command_parsing(self):
        script = (
            'python3 manage.py migrate --noinput\n'
            'django-admin seed_taxonomy\n'
            'python -m django validate_taxonomy\n'
            'exec "$@"\n'
        )
        self.assertEqual(_management_commands(script), ['migrate', 'seed_taxonomy', 'validate_taxonomy'])
