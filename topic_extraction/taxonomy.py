import numpy as np
from django.conf import settings

_embedding_model = None
_taxonomy_cache: dict = {}  # language_code -> (list[Topic], np.ndarray)


def get_embedding_model():
    """Get or create the embedding model using a singleton pattern.

    Loads the model specified by settings.EMBEDDING_MODEL_NAME, defaulting to
    'intfloat/multilingual-e5-base'. The model is cached in module scope and
    reused across calls.

    Returns:
        SentenceTransformer: The embedding model instance.
    """
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        model_name = getattr(settings, 'EMBEDDING_MODEL_NAME', 'intfloat/multilingual-e5-base')
        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model


def get_taxonomy_embeddings(language: str):
    """Return (topics, embeddings) for the given language, cached in memory.

    Topics are loaded from the DB. Labels are taken from Topic.labels[language],
    falling back to Topic.label_en if no translation exists.

    Args:
        language: ISO 639-1 language code.

    Returns:
        Tuple of (list[Topic], np.ndarray of shape [n_topics, embedding_dim]).
    """
    if language not in _taxonomy_cache:
        from topic_extraction.models import Topic
        topics = list(Topic.objects.filter(parent__isnull=False, is_active=True))
        if not topics:
            raise RuntimeError(
                'No active leaf topics. Run: python manage.py seed_taxonomy'
            )
        labels = [t.labels.get(language) or t.label_en for t in topics]
        model = get_embedding_model()
        embeddings = model.encode(labels, convert_to_numpy=True, normalize_embeddings=True)
        _taxonomy_cache[language] = (topics, embeddings)
    return _taxonomy_cache[language]


def invalidate_taxonomy_cache():
    """Clear the in-memory taxonomy cache. Call after Topic table changes."""
    global _taxonomy_cache
    _taxonomy_cache = {}


def get_topics_for_listing(language: str) -> dict:
    """Return active parents + leaves + hierarchy for GET /api/topics.

    Format:
        {
            'parents': {slug: localized_label, ...},
            'leaves': {slug: localized_label, ...},
            'hierarchy': {leaf_slug: parent_slug, ...},
        }

    Localized label falls back to label_en if the language is not in labels dict.
    """
    from topic_extraction.models import Topic

    parents_qs = Topic.objects.filter(parent__isnull=True, is_active=True)
    leaves_qs = Topic.objects.filter(parent__isnull=False, is_active=True).select_related('parent')

    parents = {p.slug: (p.labels.get(language) or p.label_en) for p in parents_qs}
    leaves = {l.slug: (l.labels.get(language) or l.label_en) for l in leaves_qs}
    hierarchy = {l.slug: l.parent.slug for l in leaves_qs}

    return {'parents': parents, 'leaves': leaves, 'hierarchy': hierarchy}
