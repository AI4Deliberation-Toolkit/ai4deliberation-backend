import os

from topic_extraction.ingestors.base import BaseIngestor, Conversation


def iter_articles(source_path=None):
    """Module-level iteration helper used by backfill_embeddings.

    Yields one dict per article: {'platform', 'article_id', 'article', 'comments'}.
    Default source_path resolves to the production parquet location under
    settings.BASE_DIR (override-able via OPENGOV_PARQUET_PATH setting).
    """
    if source_path is None:
        from django.conf import settings
        default_path = os.path.join(
            getattr(settings, 'BASE_DIR', os.getcwd()),
            'resources', 'deliberations', 'opengov_deliberations_v2.parquet',
        )
        source_path = getattr(settings, 'OPENGOV_PARQUET_PATH', default_path)

    ingestor = OpengovIngestor()
    for c in ingestor.load(source_path):
        yield {
            'platform': c.platform,
            'article_id': c.article_id,
            'article': c.article,
            'comments': c.comments,
        }


class OpengovIngestor(BaseIngestor):
    """Ingestor for opengov.gr deliberation parquet files.

    Yields one Conversation per article. Comments and documents from the
    parquet schema are intentionally ignored; corpus passes that need
    comment-level signal should use a different ingestor or extend this one.

    The article_id key is "{consultation_id}:{article_id}" — stable across
    runs and unique within a parquet.
    """

    def __init__(self, platform: str = 'opengov'):
        self.platform = platform

    def load(self, source: str) -> list[Conversation]:
        if not os.path.exists(source):
            raise FileNotFoundError(f'Parquet source not found: {source!r}')

        import pyarrow.parquet as pq

        table = pq.read_table(source, columns=['consultation_id', 'articles'])
        rows = table.to_pylist()

        conversations: list[Conversation] = []
        for row in rows:
            consultation_id = row['consultation_id']
            for article in row.get('articles') or []:
                title = (article.get('title') or '').strip()
                body = (article.get('body_text') or '').strip()
                if not title and not body:
                    continue
                # Anonymization hook: scrub title/body here before assembling
                # the Conversation when post_to_external services becomes
                # part of the corpus_pass flow. See topic_extraction/anonymization.py.
                article_text = f'{title}\n\n{body}'.strip() if title and body else (title or body)
                conversations.append(Conversation(
                    article_id=f'{consultation_id}:{article["article_id"]}',
                    platform=self.platform,
                    article=article_text,
                    comments=[],
                ))
        return conversations
