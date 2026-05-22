"""One-shot bulk-embedding command for historical articles.

Iterates an ingestor source, looks up matching ArticleTopic rows, computes
the passage embedding via the shared _compute_passage_embedding helper, and
UPSERTs the ArticleEmbedding row.

See docs/superpowers/specs/2026-05-21-article-similarity-design.md section
3 (Embedding write path → Backfill) for the full design.

Note: per-article writes are independent; no outer transaction wraps the
loop so a single bad row does not roll back the rest. The per-row try/
except in `handle` increments the `failed` counter and continues.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from topic_extraction.extractors.embedding import _compute_passage_embedding
from topic_extraction.models import ArticleEmbedding, ArticleTopic


def _get_ingestor(source_name: str):
    """Return the ingestor module for the given source name.

    For Phase 4 v1, only 'opengov' is supported. Extend the if/elif when
    adding new platforms.
    """
    if source_name == 'opengov':
        from topic_extraction.ingestors import opengov
        return opengov
    raise CommandError(f'Unknown source: {source_name!r}')


class Command(BaseCommand):
    help = (
        'Bulk-embed historical articles into ArticleEmbedding. '
        'Iterates the source ingestor, computes embeddings, UPSERTs. '
        'See spec docs/superpowers/specs/2026-05-21-article-similarity-design.md.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True,
                            help='Ingestor name (e.g. opengov).')
        parser.add_argument('--platform', default=None,
                            help='Limit to one platform.')
        parser.add_argument('--language', default=None,
                            help='Limit to one language.')
        parser.add_argument('--only-missing', action='store_true',
                            help='Skip articles that already have an ArticleEmbedding row.')
        parser.add_argument('--where-model', default=None,
                            help='Only re-embed rows currently stamped with this model name.')

    def handle(self, *args, **options):
        source_name = options['source']
        platform_filter = options['platform']
        language_filter = options['language']
        only_missing = options['only_missing']
        where_model = options['where_model']

        ingestor = _get_ingestor(source_name)

        created = 0
        updated = 0
        skipped_no_articletopic = 0
        skipped_only_missing = 0
        skipped_where_model = 0
        failed = 0

        try:
            for article_data in ingestor.iter_articles():
                try:
                    platform = article_data['platform']
                    article_id = article_data['article_id']
                    article_text = article_data['article']
                    comments = article_data.get('comments', [])

                    if platform_filter and platform != platform_filter:
                        continue

                    at = ArticleTopic.objects.filter(
                        platform=platform, article_id=article_id
                    ).order_by('-computed_at').first()
                    if at is None:
                        skipped_no_articletopic += 1
                        continue

                    if language_filter and at.language != language_filter:
                        continue

                    existing = ArticleEmbedding.objects.filter(
                        platform=platform, article_id=article_id
                    ).first()

                    if only_missing and existing is not None:
                        skipped_only_missing += 1
                        continue

                    if where_model is not None:
                        if existing is None or existing.embedding_model_name != where_model:
                            skipped_where_model += 1
                            continue

                    passage_emb = _compute_passage_embedding(
                        article_text, comments, at.language
                    )

                    _, was_created = ArticleEmbedding.objects.update_or_create(
                        platform=platform,
                        article_id=article_id,
                        defaults={
                            'language': at.language,
                            'vector': passage_emb.tolist(),
                            'embedding_model_name': settings.EMBEDDING_MODEL_NAME,
                        }
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

                except Exception as e:
                    failed += 1
                    self.stderr.write(
                        f'  FAILED ({type(e).__name__}): '
                        f'{article_data.get("platform", "?")}/{article_data.get("article_id", "?")} — {e}'
                    )
        except FileNotFoundError as e:
            raise CommandError(f'Source file not found: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created: {created}, updated: {updated}, '
            f'skipped (no ArticleTopic): {skipped_no_articletopic}, '
            f'skipped (--only-missing): {skipped_only_missing}, '
            f'skipped (--where-model): {skipped_where_model}, '
            f'failed: {failed}'
        ))
