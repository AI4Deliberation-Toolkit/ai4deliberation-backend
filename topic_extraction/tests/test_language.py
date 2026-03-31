from django.test import TestCase
from unittest.mock import patch
from topic_extraction.language import detect_language


class DetectLanguageTest(TestCase):
    def test_detects_greek(self):
        greek_text = 'Η εκπαιδευτική πολιτική είναι σημαντική για τη χώρα μας.'
        result = detect_language(greek_text)
        self.assertEqual(result, 'el')

    def test_detects_english(self):
        english_text = 'The education policy is very important for our country.'
        result = detect_language(english_text)
        self.assertEqual(result, 'en')

    def test_returns_fallback_on_very_short_text(self):
        result = detect_language('???', fallback='en')
        self.assertEqual(result, 'en')

    def test_uses_article_and_first_three_comments(self):
        with patch('topic_extraction.language.detect') as mock_detect:
            mock_detect.return_value = 'el'
            detect_language('article text', ['c1', 'c2', 'c3', 'c4', 'c5'])
            # Should concatenate article + first 3 comments only
            called_text = mock_detect.call_args[0][0]
            self.assertIn('c1', called_text)
            self.assertIn('c3', called_text)
            self.assertNotIn('c4', called_text)
