from dataclasses import dataclass

import numpy as np
from sentence_transformers import util

from topic_extraction.extractors.base import TopicResult
from topic_extraction.taxonomy import get_embedding_model, get_taxonomy_embeddings


@dataclass
class NormalizedTopic:
    topic_id: str  # Topic.slug
    score: float
    raw_score: float | None = None


def normalize(
    raw_topics: list[TopicResult],
    language: str,
    threshold: float = 0.5,
) -> list[NormalizedTopic]:
    """Map free-form extracted topics to canonical taxonomy nodes.

    Each raw topic label is embedded and matched against precomputed taxonomy
    embeddings. If multiple raw topics map to the same taxonomy node, the
    highest score is kept.

    Args:
        raw_topics: Output from an extractor.
        language: ISO 639-1 code used to select taxonomy label translations.
        threshold: Minimum cosine similarity to accept a match.

    Returns:
        Deduplicated list of NormalizedTopic sorted by score descending.
    """
    if not raw_topics:
        return []

    model = get_embedding_model()
    raw_labels = [t.label for t in raw_topics]
    raw_embeddings = model.encode(raw_labels, convert_to_numpy=True, normalize_embeddings=True)

    topics, taxonomy_embeddings = get_taxonomy_embeddings(language)

    best: dict[str, NormalizedTopic] = {}
    for raw_emb, raw_topic in zip(raw_embeddings, raw_topics):
        # raw_emb is 1D, need to reshape to 2D for cos_sim
        scores = util.cos_sim(raw_emb.reshape(1, -1), taxonomy_embeddings)[0].numpy()
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        if best_score >= threshold:
            slug = topics[best_idx].slug
            if slug not in best or best[slug].score < raw_topic.score:
                best[slug] = NormalizedTopic(
                    topic_id=slug,
                    score=round(raw_topic.score, 4),
                    raw_score=raw_topic.raw_score,
                )

    return sorted(best.values(), key=lambda x: x.score, reverse=True)
