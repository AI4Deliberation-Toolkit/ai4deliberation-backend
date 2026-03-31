from django.test import TestCase
from topic_extraction.extractors.base import BaseExtractor, TopicResult


class TopicResultTest(TestCase):
    def test_topic_result_fields(self):
        t = TopicResult(label='education policy', score=0.85)
        self.assertEqual(t.label, 'education policy')
        self.assertEqual(t.score, 0.85)

    def test_base_extractor_is_abstract(self):
        with self.assertRaises(TypeError):
            BaseExtractor()

    def test_concrete_extractor_must_implement_extract(self):
        class Incomplete(BaseExtractor):
            pass
        with self.assertRaises(TypeError):
            Incomplete()
