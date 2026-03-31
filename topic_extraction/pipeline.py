from django.conf import settings

from topic_extraction.extractors.base import BaseExtractor
from topic_extraction.extractors.embedding import EmbeddingExtractor
from topic_extraction.language import detect_language
from topic_extraction.models import ArticleTopic
from topic_extraction.normalizer import normalize


def _get_extractor() -> BaseExtractor:
    backend = getattr(settings, 'EXTRACTION_BACKEND', 'embedding')
    if backend == 'llm':
        from topic_extraction.extractors.llm import LLMExtractor
        return LLMExtractor()
    from topic_extraction.extractors.embedding import EmbeddingExtractor
    return EmbeddingExtractor()


def run(article_id: str, platform: str, article: str, comments: list[str]) -> ArticleTopic:
    """Run the full topic extraction pipeline for a single conversation.

    Detects language, extracts free-form topics, normalises to taxonomy,
    and persists an ArticleTopic record. LLM failures fall back to
    EmbeddingExtractor automatically.

    Args:
        article_id: Opaque external identifier from the source platform.
        platform: Pilot site identifier.
        article: Main article or section text.
        comments: List of comment strings (threading already flattened).

    Returns:
        Newly created ArticleTopic instance.
    """
    language = detect_language(article, comments)

    extractor = _get_extractor()
    backend = getattr(settings, 'EXTRACTION_BACKEND', 'embedding')
    try:
        raw_topics = extractor.extract(article, comments, language)
    except Exception:
        raw_topics = EmbeddingExtractor().extract(article, comments, language)
        backend = 'embedding'

    normalized = normalize(raw_topics, language)

    return ArticleTopic.objects.create(
        article_id=article_id,
        platform=platform,
        language=language,
        raw_topics=[{'label': t.label, 'score': t.score} for t in raw_topics],
        normalized=[{'topic_id': n.topic_id, 'score': n.score} for n in normalized],
        backend=backend,
    )
