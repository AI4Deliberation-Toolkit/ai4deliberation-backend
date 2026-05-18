import logging
from django.test import TestCase, override_settings
from topic_extraction.language import detect_language


@override_settings(TOPIC_LANGUAGES=['en', 'el', 'de'], DEFAULT_LANGUAGE='en', LANG_DETECT_MIN_CHARS=30)
class DetectLanguageTest(TestCase):
    def test_explicit_supported_language_used(self):
        lang, source = detect_language('hello world', explicit='el')
        self.assertEqual(lang, 'el')
        self.assertEqual(source, 'explicit')

    def test_explicit_unsupported_raises(self):
        with self.assertRaises(ValueError):
            detect_language('hello world', explicit='fr')

    def test_detected_supported(self):
        # A clearly Greek passage longer than 30 chars
        text = 'Αυτό είναι ένα δοκιμαστικό κείμενο για ανίχνευση γλώσσας στα ελληνικά.'
        lang, source = detect_language(text)
        self.assertEqual(lang, 'el')
        self.assertEqual(source, 'detected')

    def test_detected_unsupported_falls_back_to_default(self):
        # French passage; detection should succeed but result not in TOPIC_LANGUAGES.
        # The contract includes emitting a warning log with the detected code so
        # operators can see unsupported languages arriving in production.
        text = "Ceci est un texte de test en français pour la détection de la langue parlée."
        with self.assertLogs('topic_extraction.language', level='WARNING') as cm:
            lang, source = detect_language(text)
        self.assertEqual(lang, 'en')
        self.assertEqual(source, 'default')
        self.assertTrue(any('Unsupported language detected: fr' in m for m in cm.output),
                        f'Expected warning naming detected code, got: {cm.output}')

    def test_short_text_skips_detection(self):
        lang, source = detect_language('hi')  # < 30 chars
        self.assertEqual(lang, 'en')
        self.assertEqual(source, 'default')

    def test_failed_detection_falls_back(self):
        # Pathological input that may crash langdetect
        text = '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        lang, source = detect_language(text)
        self.assertEqual(lang, 'en')
        self.assertEqual(source, 'default')
