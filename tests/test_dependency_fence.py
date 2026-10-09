"""Keeps the gateway thin: no ML/NLP imports may creep back into this repo."""
import ast
import re
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

# Gitignored, local-only folders that may hold old experiment code.
SKIPPED_DIRS = {'docs', 'resources', 'scripts', 'staticfiles', 'media', 'venv', 'env', 'myenv', 'ENV', 'node_modules'}


def _project_python_files():
    for path in ROOT.rglob('*.py'):
        parts = path.relative_to(ROOT).parts
        if any(part.startswith('.') or part in SKIPPED_DIRS for part in parts):
            continue
        yield path


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
        names = []
        for line in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines():
            line = line.split('#', 1)[0].strip()
            if line:
                names.append(re.split(r'[<>=!~\[;\s]', line, maxsplit=1)[0].lower())
        self.assertEqual(sorted(set(names) & BANNED_REQUIREMENTS), [])

    def test_entrypoint_only_calls_existing_commands(self):
        script = (ROOT / 'docker' / 'web' / 'entrypoint.sh').read_text(encoding='utf-8')
        called = re.findall(r'manage\.py\s+([a-z_]+)', script)
        self.assertTrue(called, 'entrypoint no longer calls manage.py at all')
        unknown = sorted(set(called) - set(get_commands()))
        self.assertEqual(unknown, [], f'entrypoint calls unknown management commands: {unknown}')
