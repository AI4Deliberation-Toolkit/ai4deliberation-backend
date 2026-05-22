from django.conf import settings
from sentence_transformers import util
from transformers import pipeline as hf_pipeline
import numpy as np

from topic_extraction.extractors.base import BaseExtractor, TopicResult
from topic_extraction.taxonomy import get_embedding_model, get_taxonomy_embeddings


def _compute_passage_embedding(article: str, comments: list[str], language: str) -> np.ndarray:
    """Shared passage-embedding computation used by both live extraction and
    backfill. Concatenates article + first 20 comments and runs the embedding
    model (`get_embedding_model`, which honors `settings.EMBEDDING_MODEL_NAME`).
    Returns a normalized numpy vector ready for cosine similarity.

    `language` is accepted but unused — kept in the signature so a future
    language-specific encoder swap can use it without changing call sites.

    Used by:
    - _compute_similarity_scores (below) for live extraction in the same call.
    - topic_extraction/management/commands/backfill_embeddings.py for bulk
      historical backfill. Bit-identical output for the same input is a
      load-bearing invariant — tests in test_extractors.py and the end-to-end
      parity test in test_backfill_embeddings.py lock it down.
    """
    passage = article + ' ' + ' '.join(comments[:20])
    model = get_embedding_model()
    return model.encode([passage], convert_to_numpy=True, normalize_embeddings=True)[0]


def _compute_similarity_scores(article: str, comments: list[str], language: str):
    """Shared first stage: passage embedding → cosine similarity vs taxonomy.

    Returns (topics, candidate_labels, emb_scores).
    """
    topics, taxonomy_embeddings = get_taxonomy_embeddings(language)
    candidate_labels = [t.labels.get(language) or t.label_en for t in topics]
    passage_emb = _compute_passage_embedding(article, comments, language)
    emb_scores = util.cos_sim(passage_emb, taxonomy_embeddings)[0].numpy()
    return topics, candidate_labels, emb_scores


class EmbeddingSimilarityExtractor(BaseExtractor):
    """Fast CPU-friendly extractor using embedding cosine similarity, ranked by
    per-article z-score normalisation.

    For each article, the raw cosine similarities against the 91 leaf
    embeddings are z-score-normalised against the article's own mean and
    stdev. Results are filtered by `settings.EMBEDDING_Z_THRESHOLD` (default
    1.0 — one stdev above the article's baseline) and sorted by z-score
    descending. Both the raw cosine and the z-score are returned on each
    TopicResult so downstream callers can use either signal.

    Why z-score: on civic-policy corpora, raw cosine similarities cluster in
    a narrow band (~0.77-0.87 on Greek opengov text under
    paraphrase-multilingual-mpnet) that defeats absolute thresholds. Z-score
    normalisation surfaces relative fit: an article where one leaf is 2σ
    above its own mean has a clearly-best match even when absolute scores
    look similar to every other article in the corpus. See deferred-decisions
    entry #6 for the empirical evidence (2026-05-20 corpus runs).

    No zero-shot NLI step — ~50x faster per article than EmbeddingExtractor
    on CPU. Use for exploratory corpus passes, taxonomy refinement, and
    throughput-bound batches.
    """

    def extract(self, article: str, comments: list[str], language: str = 'en') -> list[TopicResult]:
        """Topics-only wrapper preserved for backwards compatibility. Direct
        callers (like the legacy `pipeline.run` path before Task 4) get the
        same shape they did before. New callers wanting the passage embedding
        for persistence should use `extract_with_embedding`."""
        topics, _passage_emb = self.extract_with_embedding(article, comments, language)
        return topics

    def extract_with_embedding(self, article: str, comments: list[str], language: str = 'en') -> tuple[list[TopicResult], np.ndarray]:
        """Returns (topics, passage_embedding). The passage_embedding is the
        same vector used internally for taxonomy similarity scoring — exposed
        here so the pipeline can persist it to ArticleEmbedding without
        recomputing. Bit-identical to _compute_passage_embedding(article,
        comments, language)."""
        # We can't reuse _compute_similarity_scores wholesale because it
        # returns (topics, candidate_labels, emb_scores), not the vector
        # itself. So compute the vector via the shared helper and then
        # replicate the scoring logic over emb_scores using the same
        # taxonomy data.
        passage_emb = _compute_passage_embedding(article, comments, language)
        topics, taxonomy_embeddings = get_taxonomy_embeddings(language)
        candidate_labels = [t.labels.get(language) or t.label_en for t in topics]
        emb_scores = util.cos_sim(passage_emb, taxonomy_embeddings)[0].numpy()

        mean = float(np.mean(emb_scores))
        std = float(np.std(emb_scores))
        if std == 0.0:
            return [], passage_emb  # Degenerate; still return the vector.

        z_scores = (emb_scores - mean) / std
        z_threshold = getattr(settings, 'EMBEDDING_Z_THRESHOLD', 1.0)

        results = []
        for i in range(len(topics)):
            z = float(z_scores[i])
            if z >= z_threshold:
                results.append(TopicResult(
                    label=candidate_labels[i],
                    score=round(z, 4),
                    raw_score=round(float(emb_scores[i]), 4),
                ))
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:10], passage_emb


class EmbeddingExtractor(BaseExtractor):
    """CPU-safe extractor combining embedding similarity with zero-shot NLI.

    The zero-shot signal cross-checks the embedding score to suppress false
    positives — at the cost of N candidate-label NLI forward passes per
    article. Production default; for fast exploratory work prefer
    EmbeddingSimilarityExtractor.
    """

    def __init__(self):
        self._zero_shot_pipeline = None

    def _get_zero_shot(self):
        if self._zero_shot_pipeline is None:
            model_name = getattr(
                settings, 'ZERO_SHOT_MODEL_NAME', 'MoritzLaurer/mDeBERTa-v3-base-mnli-xnli'
            )
            self._zero_shot_pipeline = hf_pipeline('zero-shot-classification', model=model_name)
        return self._zero_shot_pipeline

    def extract(self, article: str, comments: list[str], language: str = 'en') -> list[TopicResult]:
        topics, _passage_emb = self.extract_with_embedding(article, comments, language)
        return topics

    def extract_with_embedding(self, article: str, comments: list[str], language: str = 'en') -> tuple[list[TopicResult], np.ndarray]:
        passage_emb = _compute_passage_embedding(article, comments, language)
        topics, taxonomy_embeddings = get_taxonomy_embeddings(language)
        candidate_labels = [t.labels.get(language) or t.label_en for t in topics]
        emb_scores = util.cos_sim(passage_emb, taxonomy_embeddings)[0].numpy()

        zs = self._get_zero_shot()
        article_truncated = article[:1000]
        zs_result = zs(article_truncated, candidate_labels, multi_label=True)
        zs_score_map = dict(zip(zs_result['labels'], zs_result['scores']))

        threshold = getattr(settings, 'EMBEDDING_THRESHOLD', 0.35)
        results = []
        for i, topic in enumerate(topics):
            label = candidate_labels[i]
            emb_score = float(emb_scores[i])
            zs_score = float(zs_score_map.get(label, 0.0))
            avg_score = (emb_score + zs_score) / 2
            if avg_score >= threshold:
                results.append(TopicResult(label=label, score=round(avg_score, 4)))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:10], passage_emb
