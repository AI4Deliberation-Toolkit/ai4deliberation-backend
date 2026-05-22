from django.conf import settings
from django.db import transaction

from topic_extraction.extractors.base import BaseExtractor
from topic_extraction.language import detect_language
from topic_extraction.models import ArticleTopic, ArticleEmbedding
from topic_extraction.normalizer import normalize
from topic_extraction.taxonomy_data import TAXONOMY_VERSION


def _get_extractor(backend_override: str | None = None) -> BaseExtractor:
    backend = backend_override or getattr(settings, 'EXTRACTION_BACKEND', 'embedding')
    if backend == 'llm':
        from topic_extraction.extractors.llm import LLMExtractor
        return LLMExtractor()
    if backend == 'embedding_similarity':
        from topic_extraction.extractors.embedding import EmbeddingSimilarityExtractor
        return EmbeddingSimilarityExtractor()
    from topic_extraction.extractors.embedding import EmbeddingExtractor
    return EmbeddingExtractor()


def extract(
    article_id: str,
    platform: str,
    article: str,
    comments: list[str],
    explicit_language: str | None = None,
    backend: str | None = None,
) -> dict:
    """Detect language → extract → normalize. Returns the payload that would
    be written to ArticleTopic (plus a new `passage_embedding` field for the
    ArticleEmbedding write), but does NOT persist.

    Used by corpus_pass and other read-only flows that want extraction
    results without DB side effects.

    The returned dict has the same keys as before, plus:
        passage_embedding: list[float] | None
            The article+comments passage vector if the extractor produced one
            (embedding-based backends), else None. Callers wishing to persist
            it (like `run` below) write it to ArticleEmbedding; corpus_pass
            and similar may discard.

    Args:
        backend: Optional backend override ('embedding', 'embedding_similarity',
            'llm'). Defaults to settings.EXTRACTION_BACKEND.
    """
    language, language_source = detect_language(article, comments, explicit=explicit_language)

    extractor = _get_extractor(backend)
    effective_backend = backend or getattr(settings, 'EXTRACTION_BACKEND', 'embedding')
    passage_emb = None
    try:
        if hasattr(extractor, 'extract_with_embedding'):
            raw_topics, passage_emb = extractor.extract_with_embedding(article, comments, language)
        else:
            raw_topics = extractor.extract(article, comments, language)
    except Exception:
        # Fallback path: EmbeddingExtractor (the slow zero-shot one) is the
        # safety net. Its extract_with_embedding produces a vector in the real
        # implementation; tests may mock this to None for convenience.
        from topic_extraction.extractors.embedding import EmbeddingExtractor
        raw_topics, passage_emb = EmbeddingExtractor().extract_with_embedding(article, comments, language)
        effective_backend = 'embedding'

    normalized = normalize(raw_topics, language)

    return {
        'article_id': article_id,
        'platform': platform,
        'language': language,
        'language_source': language_source,
        'raw_topics': [
            {'label': t.label, 'score': t.score, 'raw_score': t.raw_score}
            for t in raw_topics
        ],
        'normalized': [
            {'topic_id': n.topic_id, 'score': n.score, 'raw_score': n.raw_score}
            for n in normalized
        ],
        'backend': effective_backend,
        'taxonomy_version': TAXONOMY_VERSION,
        'passage_embedding': passage_emb.tolist() if passage_emb is not None else None,
    }


def run(
    article_id: str,
    platform: str,
    article: str,
    comments: list[str],
    explicit_language: str | None = None,
    backend: str | None = None,
) -> ArticleTopic:
    """Detect language → extract → normalize → persist a new ArticleTopic row.
    Also UPSERTs an ArticleEmbedding row in the same transaction when the
    extractor produced a passage embedding (i.e. for embedding-based backends).

    Args:
        article_id: External identifier from the source platform.
        platform: Pilot site identifier.
        article: Main text.
        comments: Flattened list of comment strings.
        explicit_language: Optional ISO 639-1 override. If supplied, bypasses
            auto-detection. Must be in settings.TOPIC_LANGUAGES.

    Returns:
        The newly created ArticleTopic.

    Raises:
        ValueError: if explicit_language is not in settings.TOPIC_LANGUAGES.
    """
    payload = extract(article_id, platform, article, comments, explicit_language, backend)
    # Pop the embedding field; ArticleTopic doesn't have a vector column.
    passage_embedding = payload.pop('passage_embedding', None)

    with transaction.atomic():
        record = ArticleTopic.objects.create(**payload)
        if passage_embedding is not None:
            ArticleEmbedding.objects.update_or_create(
                platform=platform,
                article_id=article_id,
                defaults={
                    'language': payload['language'],
                    'vector': passage_embedding,
                    'embedding_model_name': settings.EMBEDDING_MODEL_NAME,
                },
            )
    return record
