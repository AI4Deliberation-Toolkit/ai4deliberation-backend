import re
from django.test import TestCase
from topic_extraction import taxonomy_data


class TaxonomyVersionTest(TestCase):
    def test_taxonomy_version_constant_exists(self):
        self.assertTrue(hasattr(taxonomy_data, 'TAXONOMY_VERSION'))

    def test_taxonomy_version_format(self):
        # Format: YYYY-MM-DD-N
        self.assertRegex(taxonomy_data.TAXONOMY_VERSION, r'^\d{4}-\d{2}-\d{2}-\d+$')
