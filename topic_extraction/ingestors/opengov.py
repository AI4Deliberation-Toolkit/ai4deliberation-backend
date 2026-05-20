import os

from topic_extraction.ingestors.base import BaseIngestor, Conversation


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
