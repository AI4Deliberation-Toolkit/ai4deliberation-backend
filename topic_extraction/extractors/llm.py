import json
import re

from django.conf import settings
from transformers import pipeline

from topic_extraction.extractors.base import BaseExtractor, TopicResult


class LLMExtractor(BaseExtractor):
    """GPU extractor using a small instruction-tuned LLM (Qwen2.5-3B or similar).

    Prompts the model to extract topics as JSON in the detected input language.
    Falls back to ValueError on parse failure — the pipeline catches this and
    delegates to EmbeddingExtractor.
    """

    def __init__(self):
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            import torch
            model_name = getattr(settings, 'LLM_MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
            self._pipeline = pipeline(
                'text-generation',
                model=model_name,
                torch_dtype=torch.float16,
                device_map='auto',
            )
        return self._pipeline

    def _build_prompt(self, article: str, comments: list[str], language: str) -> str:
        article_part = article[:1000]
        comments_part = '\n'.join(comments)[:1000]
        return (
            'You are a topic extraction assistant. '
            'Read the following article and comments and extract the main topics discussed. '
            'Respond ONLY with a valid JSON array of objects with "label" and "score" (0.0-1.0) fields. '
            f'Respond in the same language as the text (language code: {language}). '
            'Example: [{"label": "topic name", "score": 0.9}]\n\n'
            f'Article:\n{article_part}\n\n'
            f'Comments:\n{comments_part}\n\n'
            'Topics JSON:'
        )

    def extract(self, article: str, comments: list[str], language: str = 'en') -> list[TopicResult]:
        pipe = self._get_pipeline()
        prompt = self._build_prompt(article, comments, language)
        output = pipe(prompt, max_new_tokens=512, do_sample=False)[0]['generated_text']

        generated = output[len(prompt):]
        json_match = re.search(r'\[.*?\]', generated, re.DOTALL)
        if not json_match:
            raise ValueError(f'LLM did not return valid JSON: {generated[:200]}')

        try:
            raw = json.loads(json_match.group())
        except json.JSONDecodeError as exc:
            raise ValueError(f'LLM did not return valid JSON: {generated[:200]}') from exc
        return [
            TopicResult(label=item['label'], score=float(item['score']))
            for item in raw
            if 'label' in item and 'score' in item
        ]
