from django.conf import settings

from topic_extraction.extractors.base import BaseExtractor
from topic_extraction.language import detect_language
from topic_extraction.models import ArticleTopic
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
    be written to ArticleTopic, but does NOT persist.

    Used by corpus_pass and other read-only flows that want extraction
    results without DB side effects.

    Args:
        backend: Optional backend override ('embedding', 'embedding_similarity',
            'llm'). Defaults to settings.EXTRACTION_BACKEND.
    """
    language, language_source = detect_language(article, comments, explicit=explicit_language)

    extractor = _get_extractor(backend)
    effective_backend = backend or getattr(settings, 'EXTRACTION_BACKEND', 'embedding')
    try:
        raw_topics = extractor.extract(article, comments, language)
    except Exception:
        from topic_extraction.extractors.embedding import EmbeddingExtractor
        raw_topics = EmbeddingExtractor().extract(article, comments, language)
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
    return ArticleTopic.objects.create(**payload)
