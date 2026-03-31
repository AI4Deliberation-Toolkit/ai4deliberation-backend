from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from topic_extraction.models import Topic


class SeedTaxonomyCommandTest(TestCase):
    def test_creates_expected_topic_count(self):
        """First run should create exactly 72 topics from INITIAL_TOPICS."""
        out = StringIO()
        call_command('seed_taxonomy', stdout=out)
        self.assertEqual(Topic.objects.count(), 72)
        self.assertIn('Created: 72', out.getvalue())

    def test_is_idempotent(self):
        """Re-running the command should not create duplicates."""
        # First run
        call_command('seed_taxonomy')
        # Second run
        out = StringIO()
        call_command('seed_taxonomy', stdout=out)
        # Should still have 72 topics
        self.assertEqual(Topic.objects.count(), 72)
        # Output should indicate all were skipped
        self.assertIn('skipped (already exist): 72', out.getvalue())

    def test_topics_have_correct_label_en(self):
        """Created topics should have correct label_en values."""
        call_command('seed_taxonomy')
        # Test a few known topics
        democracy = Topic.objects.get(slug='democracy')
        self.assertEqual(democracy.label_en, 'Democracy')

        climate_change = Topic.objects.get(slug='climate_change')
        self.assertEqual(climate_change.label_en, 'Climate Change')

        artificial_intelligence = Topic.objects.get(slug='artificial_intelligence')
        self.assertEqual(artificial_intelligence.label_en, 'Artificial Intelligence')

    def test_topics_have_empty_labels_dict(self):
        """Created topics should have empty labels dict initially."""
        call_command('seed_taxonomy')
        # Test a few topics
        democracy = Topic.objects.get(slug='democracy')
        self.assertEqual(democracy.labels, {})

        education_policy = Topic.objects.get(slug='education_policy')
        self.assertEqual(education_policy.labels, {})

    def test_all_topics_unique_by_slug(self):
        """All created topics should have unique slugs."""
        call_command('seed_taxonomy')
        # If we get here without IntegrityError, uniqueness constraint passed
        # Also verify count matches
        self.assertEqual(Topic.objects.count(), 72)

    def test_multiple_runs_create_no_new_topics(self):
        """Running the command 3 times should result in same topic count."""
        call_command('seed_taxonomy')
        count_after_first = Topic.objects.count()

        call_command('seed_taxonomy')
        count_after_second = Topic.objects.count()

        call_command('seed_taxonomy')
        count_after_third = Topic.objects.count()

        self.assertEqual(count_after_first, 72)
        self.assertEqual(count_after_second, 72)
        self.assertEqual(count_after_third, 72)
