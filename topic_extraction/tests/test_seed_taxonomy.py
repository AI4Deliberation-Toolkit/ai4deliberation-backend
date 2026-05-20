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
        # A stale topic with a parent set (leaf) must be soft-deactivated.
        stale_parent = Topic.objects.get(slug=taxonomy_data.PARENTS[0]['slug'])
        Topic.objects.create(
            slug='stale_topic', label_en='Stale', is_active=True, parent=stale_parent
        )
        call_command('seed_taxonomy')
        stale = Topic.objects.get(slug='stale_topic')
        self.assertFalse(stale.is_active)

    def test_removed_parent_slug_is_deleted(self):
        call_command('seed_taxonomy')
        # A stale topic with no parent set (parent node) must be hard-deleted (D10).
        Topic.objects.create(slug='stale_parent_node', label_en='Stale Parent', is_active=True)
        call_command('seed_taxonomy')
        self.assertFalse(Topic.objects.filter(slug='stale_parent_node').exists())

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

    def test_stale_parent_is_deleted_when_no_active_leaves(self):
        # Seed once with the real taxonomy.
        call_command('seed_taxonomy')
        # Pick one parent and all its leaves to remove from code.
        removed_parent = taxonomy_data.PARENTS[0]
        removed_parent_slug = removed_parent['slug']
        remaining_parents = taxonomy_data.PARENTS[1:]
        remaining_leaves = [l for l in taxonomy_data.LEAVES if l['parent'] != removed_parent_slug]
        removed_leaves = [l for l in taxonomy_data.LEAVES if l['parent'] == removed_parent_slug]
        # Re-seed with the parent and its leaves removed.
        from unittest.mock import patch
        with patch.object(taxonomy_data, 'PARENTS', remaining_parents), \
             patch.object(taxonomy_data, 'LEAVES', remaining_leaves):
            call_command('seed_taxonomy')
        # The removed parent row must be hard-deleted.
        self.assertFalse(Topic.objects.filter(slug=removed_parent_slug).exists())
        # Its leaves must still be in DB but soft-deactivated.
        for leaf in removed_leaves:
            leaf_obj = Topic.objects.get(slug=leaf['slug'])
            self.assertFalse(leaf_obj.is_active)

    def test_stale_parent_with_active_leaf_reference_raises(self):
        # Seed once with the real taxonomy.
        call_command('seed_taxonomy')
        # Pick a parent to remove; manually insert a synthetic active leaf pointing at it.
        removed_parent = taxonomy_data.PARENTS[0]
        removed_parent_slug = removed_parent['slug']
        parent_obj = Topic.objects.get(slug=removed_parent_slug)
        Topic.objects.create(
            slug='phantom_leaf_for_test',
            label_en='Phantom leaf',
            parent=parent_obj,
            is_active=True,
        )
        remaining_parents = taxonomy_data.PARENTS[1:]
        remaining_leaves = [l for l in taxonomy_data.LEAVES if l['parent'] != removed_parent_slug]
        # Re-seed: the phantom leaf is not in code, Pass 3a deactivates stale leaves
        # only (parent__isnull=False AND is_active=True), but the phantom IS captured
        # by Pass 3a. However, the orphan check runs AFTER Pass 3a. The phantom leaf
        # has a non-code slug so it IS caught by Pass 3a and deactivated BEFORE the
        # parent hard-delete check. We need to test the scenario where Pass 3a misses
        # an active ref — i.e., the phantom leaf IS in remaining_leaves by slug but
        # its real parent is removed. We simulate that by keeping phantom in code leaves
        # list pointing at removed parent (so Pass 3a won't deactivate it), but
        # removed parent is not in PARENTS.
        synthetic_leaf = {
            'slug': 'phantom_leaf_for_test',
            'label_en': 'Phantom leaf',
            'parent': removed_parent_slug,
            'labels': {},
        }
        # Include phantom leaf in code so Pass 3a doesn't deactivate it; parent still removed.
        leaves_with_phantom = remaining_leaves + [synthetic_leaf]
        # But we also need phantom's parent in PARENTS for the orphan-check at the start
        # of seed_taxonomy to pass. Actually no: the orphan check only checks LEAVES against
        # PARENTS. If phantom's parent isn't in PARENTS, the command raises immediately.
        # So we test the actual scenario: phantom is in remaining_leaves (not stale) but
        # its parent slug is NOT in the new PARENTS list — that triggers the upfront
        # orphan-leaf check, not Pass 3b. Let's instead test Pass 3b directly by keeping
        # phantom_leaf_for_test OUT of LEAVES (so it's stale → deactivated by Pass 3a)
        # but we bypass Pass 3a by re-toggling it active within the transaction — which
        # we can't do from outside. The simplest valid test: ensure the CommandError path
        # fires when an active leaf survives Pass 3a. We simulate that by patching
        # Topic.objects.filter to return a non-empty active-refs list for the stale parent.
        from unittest.mock import patch
        original_filter = Topic.objects.filter

        def patched_filter(**kwargs):
            # When the orphan-check call is made for the stale parent, return a queryset
            # that includes our phantom slug, simulating that Pass 3a did not catch it.
            if kwargs.get('parent') == parent_obj and kwargs.get('is_active') is True:
                return original_filter(slug='phantom_leaf_for_test')
            return original_filter(**kwargs)

        with patch.object(taxonomy_data, 'PARENTS', remaining_parents), \
             patch.object(taxonomy_data, 'LEAVES', remaining_leaves), \
             patch.object(Topic.objects, 'filter', side_effect=patched_filter):
            with self.assertRaises(CommandError) as ctx:
                call_command('seed_taxonomy')
        self.assertIn('phantom_leaf_for_test', str(ctx.exception))
        # Transaction rolled back — removed parent row still exists.
        self.assertTrue(Topic.objects.filter(slug=removed_parent_slug).exists())

    def test_stale_leaves_still_soft_deactivate(self):
        # Sanity check: leaf-removal behavior is unchanged after the Pass 3 refactor.
        call_command('seed_taxonomy')
        # Manually create a stale leaf (not in code) that is active.
        stale_parent = Topic.objects.get(slug=taxonomy_data.PARENTS[0]['slug'])
        Topic.objects.create(
            slug='stale_leaf_for_test',
            label_en='Stale leaf',
            parent=stale_parent,
            is_active=True,
        )
        call_command('seed_taxonomy')
        stale = Topic.objects.get(slug='stale_leaf_for_test')
        self.assertFalse(stale.is_active)
        # The row must still exist (soft delete, not hard delete).
        self.assertTrue(Topic.objects.filter(slug='stale_leaf_for_test').exists())
