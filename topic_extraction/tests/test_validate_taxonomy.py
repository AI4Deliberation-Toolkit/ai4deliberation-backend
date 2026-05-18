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
        # No labels for 'el' are seeded; command should fail.
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
        # Deactivate one row, do not add 'el' translation; command should still pass
        # if all OTHER rows have 'el', which they don't here — so deactivate all without 'el'.
        for topic in Topic.objects.filter(is_active=True):
            if 'el' not in topic.labels:
                topic.is_active = False
                topic.save()
        out = StringIO()
        call_command('validate_taxonomy', stdout=out)
        self.assertIn('OK', out.getvalue())
