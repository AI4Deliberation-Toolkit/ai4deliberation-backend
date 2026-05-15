from django.test import TestCase
from django.conf import settings


class LanguageSettingsTest(TestCase):
    def test_topic_languages_includes_required_languages(self):
        self.assertIn('en', settings.TOPIC_LANGUAGES)
        self.assertIn('el', settings.TOPIC_LANGUAGES)
        self.assertIn('de', settings.TOPIC_LANGUAGES)

    def test_default_language_is_supported(self):
        self.assertIn(settings.DEFAULT_LANGUAGE, settings.TOPIC_LANGUAGES)

    def test_lang_detect_min_chars_is_positive(self):
        self.assertGreater(settings.LANG_DETECT_MIN_CHARS, 0)
