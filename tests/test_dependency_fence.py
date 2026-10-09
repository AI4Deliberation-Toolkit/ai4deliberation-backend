"""Keeps the gateway thin: no ML/NLP imports may creep back into this repo."""
import ast
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent

# Top-level module names that belong to the old NLP stack (now in ai4d-topic-toolkit).
BANNED_IMPORTS = {
    'accelerate', 'bertopic', 'fastapi', 'hdbscan', 'huggingface_hub', 'langdetect',
    'numpy', 'openpyxl', 'pandas', 'pyarrow', 'sentence_transformers', 'sentencepiece',
    'sklearn', 'tensorflow', 'tf_keras', 'torch', 'torchaudio', 'torchvision',
    'transformers', 'umap', 'xlrd',
}

# Gitignored, local-only folders that may hold old experiment code.
SKIPPED_DIRS = {'docs', 'resources', 'scripts', 'staticfiles', 'media', 'venv', 'node_modules'}


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
