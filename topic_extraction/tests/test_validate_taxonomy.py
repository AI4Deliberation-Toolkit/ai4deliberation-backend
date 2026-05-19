from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from topic_extraction.models import Topic


class ValidateTaxonomyCommandTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    @override_settings(TOPIC_LANGUAGES=['en'])
    def test_passes_when_only_english_required(self):
        # All topics have label_en, so en coverage is trivially complete.
        out = StringIO()
        call_command('validate_taxonomy', stdout=out)
        self.assertIn('OK', out.getvalue())

    @override_settings(TOPIC_LANGUAGES=['en', 'el'])
    def test_fails_when_translation_missing(self):
        # Strip the 'el' labels that were seeded, then validate should fail.
        for topic in Topic.objects.filter(is_active=True):
            topic.labels = {}
            topic.save()
        with self.assertRaises(CommandError):
            call_command('validate_taxonomy')

    @override_settings(TOPIC_LANGUAGES=['en', 'el'])
    def test_passes_when_all_translated(self):
        # Add 'el' translations to every active topic.
        for topic in Topic.objects.filter(is_active=True):
            topic.labels = {'el': f'{topic.label_en}_el'}
            topic.save()
        out = StringIO()
        call_command('validate_taxonomy', stdout=out)
        self.assertIn('OK', out.getvalue())

    @override_settings(TOPIC_LANGUAGES=['en', 'el'])
    def test_skips_deactivated_rows(self):
        # Strip 'el' from a few rows and deactivate them. Validation should still
        # pass because the validator skips deactivated rows — even though those
        # rows are missing the required 'el' label.
        for topic in Topic.objects.filter(is_active=True)[:3]:
            topic.labels = {}
            topic.is_active = False
            topic.save()
        out = StringIO()
        call_command('validate_taxonomy', stdout=out)
        self.assertIn('OK', out.getvalue())

    @override_settings(TOPIC_LANGUAGES=['en', 'el'])
    def test_empty_string_translation_counts_as_missing(self):
        # An empty-string label is operator error during seeding — must fail validation.
        for topic in Topic.objects.filter(is_active=True):
            topic.labels = {'el': ''}
            topic.save()
        with self.assertRaises(CommandError):
            call_command('validate_taxonomy')

    @override_settings(TOPIC_LANGUAGES=['en', 'el', 'de'])
    def test_partial_coverage_identifies_missing_language(self):
        # Translate to 'el' but not 'de'; only de should appear in the error.
        for topic in Topic.objects.filter(is_active=True):
            topic.labels = {'el': f'{topic.label_en}_el'}
            topic.save()
        with self.assertRaises(CommandError) as cm:
            call_command('validate_taxonomy')
        message = str(cm.exception)
        self.assertIn('missing translation for de', message)
        self.assertNotIn('missing translation for el', message)

    @override_settings(TOPIC_LANGUAGES=['en', 'el'])
    def test_error_message_identifies_slug(self):
        # Confirm the (slug, lang) pair is named in the error so operators can act on it.
        # Strip 'el' labels first so the validate command has something to complain about.
        sample_slug = Topic.objects.filter(is_active=True).first().slug
        for topic in Topic.objects.filter(is_active=True):
            topic.labels = {}
            topic.save()
        with self.assertRaises(CommandError) as cm:
            call_command('validate_taxonomy')
        message = str(cm.exception)
        self.assertIn(sample_slug, message)
        self.assertIn('missing translation for el', message)
