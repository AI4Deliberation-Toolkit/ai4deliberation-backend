from django.core.management import call_command
from django.test import TestCase
from topic_extraction import taxonomy
from topic_extraction.models import Topic


class GetTaxonomyEmbeddingsTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_returns_only_leaves(self):
        topics, _ = taxonomy.get_taxonomy_embeddings('en')
        for t in topics:
            self.assertIsNotNone(t.parent_id, f'{t.slug} has no parent — should not be in embedding set')

    def test_excludes_deactivated(self):
        # Deactivate one leaf
        leaf = Topic.objects.filter(parent__isnull=False, is_active=True).first()
        leaf.is_active = False
        leaf.save()
        taxonomy.invalidate_taxonomy_cache()
        topics, _ = taxonomy.get_taxonomy_embeddings('en')
        slugs = {t.slug for t in topics}
        self.assertNotIn(leaf.slug, slugs)


class GetTopicsForListingTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_returns_parents_leaves_hierarchy(self):
        result = taxonomy.get_topics_for_listing('en')
        self.assertIn('parents', result)
        self.assertIn('leaves', result)
        self.assertIn('hierarchy', result)
        self.assertIsInstance(result['parents'], dict)
        self.assertIsInstance(result['leaves'], dict)
        self.assertIsInstance(result['hierarchy'], dict)

    def test_excludes_deactivated_in_listing(self):
        leaf = Topic.objects.filter(parent__isnull=False, is_active=True).first()
        leaf.is_active = False
        leaf.save()
        result = taxonomy.get_topics_for_listing('en')
        self.assertNotIn(leaf.slug, result['leaves'])

    def test_hierarchy_maps_leaf_to_parent_slug(self):
        result = taxonomy.get_topics_for_listing('en')
        for leaf_slug, parent_slug in result['hierarchy'].items():
            self.assertIn(parent_slug, result['parents'])
