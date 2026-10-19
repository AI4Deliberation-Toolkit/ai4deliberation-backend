"""Opt-in contract check against a real toolkit; never runs in CI.

TOOLKIT_LIVE_URL=https://toolkit.example.org [TOOLKIT_LIVE_KEY=…] python manage.py test tests.gateway.test_toolkit_live
Note: each run creates one extraction row in that toolkit (the read checks look that row up).
"""
import os
from unittest import skipUnless

import httpx
from django.test import SimpleTestCase

from tests.gateway.support import load_fixture


@skipUnless(os.environ.get('TOOLKIT_LIVE_URL'), 'set TOOLKIT_LIVE_URL to run the live toolkit check')
class LiveToolkitContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_url = os.environ['TOOLKIT_LIVE_URL'].rstrip('/')
        cls.headers = {'X-API-Key': os.environ['TOOLKIT_LIVE_KEY']} if os.environ.get('TOOLKIT_LIVE_KEY') else {}
        # Once per run: it creates the wp-fixture/fixture-article-1 row the read checks look up.
        cls.extract_response = httpx.post(f'{cls.base_url}/api/topics/extract-conversation',
                                          json=load_fixture('extract_request.json'), headers=cls.headers, timeout=120)

    def assert_same_shape(self, body, fixture_name):
        """The fixture's top-level keys are all there, with the same JSON types."""
        for name, value in load_fixture(fixture_name).items():
            with self.subTest(fixture=fixture_name, field=name):
                self.assertIn(name, body)
                self.assertIsInstance(body[name], type(value))

    def test_extract_still_matches_the_fixture_shape(self):
        response = self.extract_response
        self.assertEqual(response.status_code, 201, response.text[:500])
        self.assert_same_shape(response.json(), 'extract_201.json')

    def test_taxonomy_matches_and_revalidates(self):
        # As the gateway sends reads (decision 13): uncompressed, so the proxy keeps the ETag strong.
        headers = {**self.headers, 'Accept-Encoding': 'identity'}
        first = httpx.get(f'{self.base_url}/api/topics', params={'language': 'el'}, headers=headers, timeout=30)
        self.assertEqual(first.status_code, 200, first.text[:500])
        self.assert_same_shape(first.json(), 'taxonomy_200.json')
        etag = first.headers['ETag']
        self.assertFalse(etag.startswith('W/'), etag)  # spec §7.3: still strong through the Runpod proxy
        self.assertEqual(etag, f'"{first.json()["version"]}-el"')
        second = httpx.get(f'{self.base_url}/api/topics', params={'language': 'el'},
                           headers={**headers, 'If-None-Match': etag}, timeout=30)
        self.assertEqual((second.status_code, second.content, second.headers.get('ETag')), (304, b'', etag))

    def test_article_topics_matches(self):
        response = httpx.get(f'{self.base_url}/api/topics/article/fixture-article-1', headers=self.headers,
                             timeout=30)
        self.assertEqual(response.status_code, 200, response.text[:500])
        self.assert_same_shape(response.json(), 'article_topics_200.json')

    def test_similar_articles_matches(self):
        response = httpx.get(f'{self.base_url}/api/articles/wp-fixture/fixture-article-1/similar',
                             params={'k': '5'}, headers=self.headers, timeout=30)
        self.assertEqual(response.status_code, 200, response.text[:500])
        self.assert_same_shape(response.json(), 'similar_articles_200.json')
