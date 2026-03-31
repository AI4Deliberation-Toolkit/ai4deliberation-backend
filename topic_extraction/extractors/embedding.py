from django.conf import settings
from sentence_transformers import util
from transformers import pipeline as hf_pipeline
import numpy as np

from topic_extraction.extractors.base import BaseExtractor, TopicResult
from topic_extraction.taxonomy import get_embedding_model, get_taxonomy_embeddings


class EmbeddingExtractor(BaseExtractor):
    """CPU-safe extractor using embedding similarity + zero-shot classification.

    Combines two signals:
    1. Cosine similarity between the passage embedding and taxonomy label embeddings.
    2. Zero-shot classification scores from mDeBERTa.

    The average of both signals is thresholded to produce final results.
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
        topics, taxonomy_embeddings = get_taxonomy_embeddings(language)
        candidate_labels = [t.labels.get(language) or t.label_en for t in topics]

        # Signal 1: embedding similarity on full passage
        passage = article + ' ' + ' '.join(comments[:20])
        model = get_embedding_model()
        passage_emb = model.encode([passage], convert_to_numpy=True, normalize_embeddings=True)[0]
        emb_scores = util.cos_sim(passage_emb, taxonomy_embeddings)[0].numpy()

        # Signal 2: zero-shot on article only (truncated to avoid token limit)
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
        return results[:10]
