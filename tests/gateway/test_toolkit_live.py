"""Opt-in contract check against a real toolkit; never runs in CI.

TOOLKIT_LIVE_URL=https://toolkit.example.org [TOOLKIT_LIVE_KEY=…] python manage.py test tests.gateway.test_toolkit_live
Note: each run creates one extraction row in that toolkit.
"""
import os
from unittest import skipUnless

import httpx
from django.test import SimpleTestCase

from tests.gateway.support import load_fixture


@skipUnless(os.environ.get('TOOLKIT_LIVE_URL'), 'set TOOLKIT_LIVE_URL to run the live toolkit check')
class LiveToolkitContractTests(SimpleTestCase):
    def test_extract_still_matches_the_fixture_shape(self):
        base_url = os.environ['TOOLKIT_LIVE_URL'].rstrip('/')
        headers = {'X-API-Key': os.environ['TOOLKIT_LIVE_KEY']} if os.environ.get('TOOLKIT_LIVE_KEY') else {}
        response = httpx.post(f'{base_url}/api/topics/extract-conversation', json=load_fixture('extract_request.json'),
                              headers=headers, timeout=120)
        self.assertEqual(response.status_code, 201, response.text[:500])
        body = response.json()
        for name, value in load_fixture('extract_201.json').items():
            with self.subTest(field=name):
                self.assertIn(name, body)
                self.assertIsInstance(body[name], type(value))
