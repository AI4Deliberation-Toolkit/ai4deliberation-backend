"""Article-to-article similarity queries against the persisted ArticleEmbedding store.

The public entry point is `find_similar`. Both the DRF view
(`ArticleSimilarityView`) and the FastAPI endpoint
(`fastapi_app.main.get_similar_articles`) call this function.

See `docs/superpowers/specs/2026-05-21-article-similarity-design.md` for the
full design — particularly section 4 (Query layer) for the algorithm and edge
cases this module implements.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
from sentence_transformers import util

from topic_extraction.models import ArticleEmbedding, ArticleTopic, Topic


@dataclass
class SimilarityResult:
    platform: str
    article_id: str
    language: str
    raw_score: float
    z_score: Optional[float]


class SourceNotFoundError(Exception):
    """Raised when the source article has no ArticleEmbedding row."""


class UnknownTopicSlugError(Exception):
    """Raised when a topic_slug filter value is not a known Topic slug."""


def find_similar(
    platform: str,
    article_id: str,
    k: int = 10,
    topic_slug: Optional[str] = None,
) -> list[SimilarityResult]:
    """Returns up to k articles in the same (platform, language) bucket as
    (platform, article_id), ranked by cosine similarity in the same
    embedding-model space as the source article.

    Args:
        platform: Source article's platform.
        article_id: Source article's id.
        k: Maximum number of results.
        topic_slug: Optional. Restrict to candidates whose latest
            ArticleTopic.normalized contains either this slug (if a leaf) or
            any active leaf under this slug (if a parent). Active-only filter.

    Raises:
        SourceNotFoundError: source article has no ArticleEmbedding row.
        UnknownTopicSlugError: topic_slug is not a known leaf or parent slug.
    """
    # 1. Fetch source.
    source = ArticleEmbedding.objects.filter(
        platform=platform, article_id=article_id
    ).first()
    if source is None:
        raise SourceNotFoundError(f'No ArticleEmbedding for {platform}/{article_id}')

    # 2. Candidate pool: same bucket + same model space, exclude self.
    candidates_qs = ArticleEmbedding.objects.filter(
        platform=platform,
        language=source.language,
        embedding_model_name=source.embedding_model_name,
    ).exclude(article_id=article_id)
    candidates = list(candidates_qs)

    # 3. Apply optional topic_slug filter.
    if topic_slug:
        candidates = _filter_by_topic_slug(candidates, topic_slug)
    if not candidates:
        return []

    # 4. Cosine ranking.
    source_vec = np.array(source.vector, dtype=np.float32)
    candidate_vectors = np.array(
        [c.vector for c in candidates], dtype=np.float32
    )
    cosine_scores = util.cos_sim(source_vec, candidate_vectors)[0].numpy()

    # 5. Z-score over the candidate pool (if large enough).
    if len(candidates) >= 10:
        mean = float(np.mean(cosine_scores))
        std = float(np.std(cosine_scores))
        if std > 0:
            z_scores: list[Optional[float]] = [
                round(float((s - mean) / std), 4) for s in cosine_scores
            ]
        else:
            z_scores = [0.0] * len(candidates)
    else:
        z_scores = [None] * len(candidates)

    # 6. Build results and sort.
    results = [
        SimilarityResult(
            platform=c.platform,
            article_id=c.article_id,
            language=c.language,
            raw_score=round(float(s), 4),
            z_score=z,
        )
        for c, s, z in zip(candidates, cosine_scores, z_scores)
    ]
    # Sort by z_score when populated, else raw_score (same order either way for
    # a fixed pool because z is monotonic in raw).
    if z_scores[0] is not None:
        results.sort(key=lambda r: r.z_score, reverse=True)
    else:
        results.sort(key=lambda r: r.raw_score, reverse=True)

    return results[:k]


def _filter_by_topic_slug(candidates, topic_slug):
    """Filter candidates to only those whose latest ArticleTopic.normalized
    contains the resolved slug set. Parent slugs expand to ACTIVE leaves under
    them. Inactive slugs never match (consistent with GET /api/topics behavior
    from Phase 1).

    See spec section 4c for full semantics.
    """
    topic = Topic.objects.filter(slug=topic_slug).first()
    if topic is None:
        raise UnknownTopicSlugError(topic_slug)

    if topic.parent_id is None:
        # Parent slug: expand to active leaves.
        matched_slugs = set(
            topic.children.filter(is_active=True).values_list('slug', flat=True)
        )
    else:
        # Leaf slug: must be active.
        if not topic.is_active:
            return []
        matched_slugs = {topic_slug}

    if not matched_slugs:
        return []

    # Pull latest ArticleTopic per (platform, article_id) for the candidate set.
    candidate_keys = {(c.platform, c.article_id) for c in candidates}
    candidate_platforms = {k[0] for k in candidate_keys}
    candidate_article_ids = {k[1] for k in candidate_keys}
    latest_topics: dict[tuple[str, str], ArticleTopic] = {}
    for at in ArticleTopic.objects.filter(
        platform__in=candidate_platforms,
        article_id__in=candidate_article_ids,
    ).order_by('-computed_at', '-id'):
        key = (at.platform, at.article_id)
        if key in candidate_keys and key not in latest_topics:
            latest_topics[key] = at

    def matches(candidate):
        at = latest_topics.get((candidate.platform, candidate.article_id))
        if at is None:
            return False
        normalized_slugs = {n.get('topic_id') for n in (at.normalized or [])}
        return bool(normalized_slugs & matched_slugs)

    return [c for c in candidates if matches(c)]
