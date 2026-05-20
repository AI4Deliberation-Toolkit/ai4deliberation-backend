"""Year-stratified topic extraction over an opengov corpus.

Writes per-article results to a resumable JSONL checkpoint plus a manifest
sibling file. Does NOT persist to the ArticleTopic table — this is an
exploratory pass for taxonomy refinement, not production ingestion.
"""
import datetime as dt
import json
import os

from django.core.management.base import BaseCommand, CommandError

from topic_extraction import pipeline
from topic_extraction.corpus_sampler import SampledArticle, sample_articles


class Command(BaseCommand):
    help = (
        'Year-stratified topic extraction over an opengov corpus. Writes per-article '
        'results to a resumable JSONL checkpoint. Does NOT persist to ArticleTopic.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, help='Path to opengov parquet file')
        parser.add_argument('--sample-size', type=int, default=1000)
        parser.add_argument('--year-min', type=int, default=2022)
        parser.add_argument('--year-max', type=int, default=2026)
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--output-dir', default='resources/deliberations')
        parser.add_argument('--resume', help='Path to existing JSONL checkpoint to continue from')
        parser.add_argument(
            '--max-articles', type=int, default=None,
            help='Stop after this many newly-processed articles (per invocation). '
            'Useful for smoke runs that should leave a strict prefix for later resume.',
        )
        parser.add_argument(
            '--backend', default=None,
            choices=['embedding_similarity', 'embedding', 'llm'],
            help='Extraction backend. Default: embedding_similarity (fast, similarity-only). '
            'Use "embedding" for the full two-signal extractor (production parity but ~50x '
            'slower on CPU).',
        )

    def handle(self, *args, **options):
        source = options['source']
        if not os.path.exists(source):
            raise CommandError(f'Source not found: {source!r}')

        if options['resume']:
            jsonl_path, sampled, backend = self._resume(options['resume'], options.get('backend'))
        else:
            backend = options.get('backend') or 'embedding_similarity'
            jsonl_path, sampled = self._new_run(source, options, backend)

        done_keys = self._read_done_keys(jsonl_path)
        remaining = [a for a in sampled if a.key not in done_keys]
        if options.get('max_articles') is not None:
            remaining = remaining[: options['max_articles']]

        self.stdout.write(f'Checkpoint: {jsonl_path}')
        self.stdout.write(
            f'Sampled: {len(sampled)}; done: {len(done_keys)}; '
            f'remaining this run: {len(remaining)}'
        )

        for i, art in enumerate(remaining, 1):
            article_text = (
                f'{art.title}\n\n{art.body_text}'
                if art.title and art.body_text
                else (art.title or art.body_text)
            )
            try:
                payload = pipeline.extract(
                    article_id=art.key,
                    platform='opengov',
                    article=article_text,
                    comments=[],
                    backend=backend,
                )
            except Exception as e:
                self.stderr.write(f'  ERROR on {art.key}: {e}')
                continue

            line = {
                'consultation_id': art.consultation_id,
                'article_id': art.article_id,
                'year': art.year,
                'extracted_at': dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                'language': payload['language'],
                'language_source': payload['language_source'],
                'raw_topics': payload['raw_topics'],
                'normalized': payload['normalized'],
                'backend': payload['backend'],
                'taxonomy_version': payload['taxonomy_version'],
            }
            with open(jsonl_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')

            if i % 10 == 0 or i == len(remaining):
                self.stdout.write(f'  [{i}/{len(remaining)}] {art.key}')

        self.stdout.write(self.style.SUCCESS('Done.'))

    def _new_run(self, source: str, options: dict, backend: str) -> tuple[str, list[SampledArticle]]:
        ts = dt.datetime.utcnow().strftime('%Y%m%dT%H%M%S')
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        jsonl_path = os.path.join(output_dir, f'corpus_run_{ts}.jsonl')
        manifest_path = os.path.join(output_dir, f'corpus_run_{ts}.manifest.json')

        sampled = sample_articles(
            source,
            sample_size=options['sample_size'],
            year_min=options['year_min'],
            year_max=options['year_max'],
            seed=options['seed'],
        )

        manifest = {
            'source': os.path.abspath(source),
            'sample_size': options['sample_size'],
            'year_min': options['year_min'],
            'year_max': options['year_max'],
            'seed': options['seed'],
            'backend': backend,
            'created_at': dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
            'sampled_keys': [a.key for a in sampled],
        }
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        # Touch JSONL so subsequent appends work cleanly even if extraction throws on row 1.
        open(jsonl_path, 'a', encoding='utf-8').close()
        return jsonl_path, sampled

    def _resume(
        self, jsonl_path: str, backend_override: str | None
    ) -> tuple[str, list[SampledArticle], str]:
        if not os.path.exists(jsonl_path):
            raise CommandError(f'Resume target not found: {jsonl_path!r}')
        manifest_path = jsonl_path[:-len('.jsonl')] + '.manifest.json'
        if not os.path.exists(manifest_path):
            raise CommandError(f'Manifest sibling not found: {manifest_path!r}')
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        sampled = sample_articles(
            manifest['source'],
            sample_size=manifest['sample_size'],
            year_min=manifest['year_min'],
            year_max=manifest['year_max'],
            seed=manifest['seed'],
        )
        backend = backend_override or manifest.get('backend') or 'embedding_similarity'
        return jsonl_path, sampled, backend

    def _read_done_keys(self, jsonl_path: str) -> set[str]:
        if not os.path.exists(jsonl_path):
            return set()
        done: set[str] = set()
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    done.add(f"{obj['consultation_id']}:{obj['article_id']}")
                except (json.JSONDecodeError, KeyError):
                    continue
        return done
