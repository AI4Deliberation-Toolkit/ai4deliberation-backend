from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from topic_extraction.models import Topic
from topic_extraction import taxonomy_data


class SeedTaxonomyCommandTest(TestCase):
    def test_creates_parents_and_leaves(self):
        out = StringIO()
        call_command('seed_taxonomy', stdout=out)
        expected_total = len(taxonomy_data.PARENTS) + len(taxonomy_data.LEAVES)
        self.assertEqual(Topic.objects.count(), expected_total)

    def test_is_idempotent(self):
        call_command('seed_taxonomy')
        first_count = Topic.objects.count()
        call_command('seed_taxonomy')
        self.assertEqual(Topic.objects.count(), first_count)

    def test_leaves_have_parent_set(self):
        call_command('seed_taxonomy')
        # Pick the first leaf, look it up, confirm parent is wired
        sample_leaf = taxonomy_data.LEAVES[0]
        leaf = Topic.objects.get(slug=sample_leaf['slug'])
        self.assertIsNotNone(leaf.parent)
        self.assertEqual(leaf.parent.slug, sample_leaf['parent'])

    def test_parents_have_no_parent(self):
        call_command('seed_taxonomy')
        sample_parent = taxonomy_data.PARENTS[0]
        parent = Topic.objects.get(slug=sample_parent['slug'])
        self.assertIsNone(parent.parent)

    def test_removed_slug_is_deactivated(self):
        call_command('seed_taxonomy')
        # Manually add a stale topic that's not in PARENTS or LEAVES
        Topic.objects.create(slug='stale_topic', label_en='Stale', is_active=True)
        call_command('seed_taxonomy')
        self.assertFalse(Topic.objects.get(slug='stale_topic').is_active)

    def test_admin_deactivation_survives_reseed(self):
        call_command('seed_taxonomy')
        sample_slug = taxonomy_data.LEAVES[0]['slug']
        leaf = Topic.objects.get(slug=sample_slug)
        leaf.is_active = False
        leaf.save()
        call_command('seed_taxonomy')
        self.assertFalse(Topic.objects.get(slug=sample_slug).is_active)

    def test_orphan_leaf_aborts(self):
        # Patch LEAVES temporarily to include a leaf pointing at a missing parent
        from unittest.mock import patch
        bad_leaves = taxonomy_data.LEAVES + [
            {'slug': 'orphan_x', 'label_en': 'Orphan', 'parent': 'no_such_parent', 'labels': {}}
        ]
        with patch.object(taxonomy_data, 'LEAVES', bad_leaves):
            with self.assertRaises(CommandError):
                call_command('seed_taxonomy')

    def test_invalidates_cache(self):
        from topic_extraction import taxonomy
        # Populate cache
        call_command('seed_taxonomy')
        _ = taxonomy.get_taxonomy_embeddings('en')  # warms cache
        self.assertIn('en', taxonomy._taxonomy_cache)
        # Re-seed; cache should be empty
        call_command('seed_taxonomy')
        self.assertNotIn('en', taxonomy._taxonomy_cache)
