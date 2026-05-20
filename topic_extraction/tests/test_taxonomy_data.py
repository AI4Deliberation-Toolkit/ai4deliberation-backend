import re
from django.test import TestCase
from topic_extraction import taxonomy_data


class TaxonomyVersionTest(TestCase):
    def test_taxonomy_version_constant_exists(self):
        self.assertTrue(hasattr(taxonomy_data, 'TAXONOMY_VERSION'))

    def test_taxonomy_version_format(self):
        # Format: YYYY-MM-DD-N
        self.assertRegex(taxonomy_data.TAXONOMY_VERSION, r'^\d{4}-\d{2}-\d{2}-\d+$')


class TaxonomyStructureTest(TestCase):
    def test_parents_is_non_empty_list_of_dicts(self):
        self.assertIsInstance(taxonomy_data.PARENTS, list)
        self.assertGreater(len(taxonomy_data.PARENTS), 0)
        for p in taxonomy_data.PARENTS:
            self.assertIn('slug', p)
            self.assertIn('label_en', p)
            self.assertIn('labels', p)

    def test_leaves_is_non_empty_list_of_dicts(self):
        self.assertIsInstance(taxonomy_data.LEAVES, list)
        self.assertGreater(len(taxonomy_data.LEAVES), 0)
        for leaf in taxonomy_data.LEAVES:
            self.assertIn('slug', leaf)
            self.assertIn('label_en', leaf)
            self.assertIn('parent', leaf)
            self.assertIn('labels', leaf)

    def test_every_leaf_references_a_parent_slug(self):
        parent_slugs = {p['slug'] for p in taxonomy_data.PARENTS}
        for leaf in taxonomy_data.LEAVES:
            self.assertIn(leaf['parent'], parent_slugs,
                          f"Leaf {leaf['slug']!r} references unknown parent {leaf['parent']!r}")

    def test_no_duplicate_slugs(self):
        all_slugs = [p['slug'] for p in taxonomy_data.PARENTS] + [leaf['slug'] for leaf in taxonomy_data.LEAVES]
        self.assertEqual(len(all_slugs), len(set(all_slugs)))

    def test_every_entry_has_greek_label(self):
        for p in taxonomy_data.PARENTS:
            self.assertIn('el', p['labels'],
                          f"Parent {p['slug']!r} is missing labels['el']")
            self.assertTrue(p['labels']['el'],
                            f"Parent {p['slug']!r} has an empty labels['el']")
        for leaf in taxonomy_data.LEAVES:
            self.assertIn('el', leaf['labels'],
                          f"Leaf {leaf['slug']!r} is missing labels['el']")
            self.assertTrue(leaf['labels']['el'],
                            f"Leaf {leaf['slug']!r} has an empty labels['el']")

    def test_every_entry_has_german_label(self):
        for p in taxonomy_data.PARENTS:
            self.assertIn('de', p['labels'],
                          f"Parent {p['slug']!r} is missing labels['de']")
            self.assertTrue(p['labels']['de'].strip(),
                            f"Parent {p['slug']!r} has an empty labels['de']")
        for leaf in taxonomy_data.LEAVES:
            self.assertIn('de', leaf['labels'],
                          f"Leaf {leaf['slug']!r} is missing labels['de']")
            self.assertTrue(leaf['labels']['de'].strip(),
                            f"Leaf {leaf['slug']!r} has an empty labels['de']")
