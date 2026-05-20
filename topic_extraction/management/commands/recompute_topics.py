from django.core.management.base import BaseCommand
from topic_extraction.extractors.base import TopicResult
from topic_extraction.models import ArticleTopic
from topic_extraction.normalizer import normalize
from topic_extraction.taxonomy import invalidate_taxonomy_cache
from topic_extraction.taxonomy_data import TAXONOMY_VERSION


class Command(BaseCommand):
    help = (
        'Re-normalize stored raw_topics against the current taxonomy. '
        'Writes a new ArticleTopic row per article reflecting the current '
        "TAXONOMY_VERSION. Does NOT re-run extraction (source text is not stored). "
        'Rows with empty raw_topics are skipped.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform', default=None,
            help='Limit re-normalization to a specific platform. Omit to cover all.'
        )

    def handle(self, *args, **options):
        platform = options['platform']
        invalidate_taxonomy_cache()

        qs = ArticleTopic.objects.all()
        if platform:
            qs = qs.filter(platform=platform)

        # Pick the latest stored row per (article_id, platform) — that has the freshest raw_topics.
        # Python-side dedupe (not .distinct(field, ...)) because SQLite, used by tests,
        # does not support distinct-on-field. Iteration is ordered newest-first, so the
        # first row seen per key is the most-recent one.
        seen = set()
        targets = []
        for record in qs.order_by('-computed_at'):
            key = (record.article_id, record.platform)
            if key not in seen:
                seen.add(key)
                targets.append(record)

        self.stdout.write(f'Re-normalizing {len(targets)} articles...')

        renormalized = 0
        skipped_empty = 0
        failed = 0

        for record in targets:
            if not record.raw_topics:
                skipped_empty += 1
                self.stdout.write(f'  skipped (empty raw_topics): {record.article_id}')
                continue

            try:
                # Stored raw_topics is JSON: list of {'label': str, 'score': number}.
                # Rehydrate into TopicResult so normalize() sees its expected input shape.
                # float() is defensive: JSON round-trip may surface scores as int.
                # Future-proofing note: extra keys on stored dicts are silently dropped
                # here. If the raw shape ever gains a third field, update this comprehension.
                raw_results = [
                    TopicResult(label=item['label'], score=float(item['score']))
                    for item in record.raw_topics
                ]
                normalized = normalize(raw_results, record.language)

                # New row mirrors the source row's stored fields (raw_topics, language,
                # language_source, backend) and stamps the current TAXONOMY_VERSION.
                # The source text is not stored, so language cannot be re-detected here;
                # carrying the stored value preserves the "re-normalize, not re-extract"
                # contract. Below-threshold results still write a row with normalized=[]
                # so operators can see the row was reconsidered.
                # Build a topic_id → raw_score map from the source row, so re-normalization
                # preserves the per-article z-score signal that fresh extractions write.
                # Re-normalization can't recompute raw_score because the article-level
                # statistics depend on the full embedding output (not stored).
                old_raw_scores = {
                    n.get('topic_id'): n.get('raw_score')
                    for n in (record.normalized or [])
                }
                normalized_payload = [
                    {
                        'topic_id': n.topic_id,
                        'score': n.score,
                        'raw_score': old_raw_scores.get(n.topic_id),
                    }
                    for n in normalized
                ]

                ArticleTopic.objects.create(
                    article_id=record.article_id,
                    platform=record.platform,
                    language=record.language,
                    language_source=record.language_source,
                    raw_topics=record.raw_topics,
                    normalized=normalized_payload,
                    backend=record.backend,
                    taxonomy_version=TAXONOMY_VERSION,
                )
                renormalized += 1
            except Exception as e:
                # Per-row isolation: an individual failure (malformed raw_topics,
                # DB constraint, etc.) is logged but does not abort the loop.
                # Operators see counts in the summary plus a stderr line per failure.
                failed += 1
                self.stderr.write(
                    f'  FAILED ({type(e).__name__}): {record.article_id} — {e}'
                )

        self.stdout.write(self.style.SUCCESS(
            f'Done. Re-normalized: {renormalized}, '
            f'skipped (empty raw_topics): {skipped_empty}, failed: {failed}'
        ))
