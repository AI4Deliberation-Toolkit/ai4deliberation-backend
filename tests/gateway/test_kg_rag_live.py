"""Opt-in contract check against the real KG RAG; never runs in CI.

Set both variables for this one command only, never export them (an exported URL would send a
live question on every full test run). Read the key without echoing it, so it stays out of the
shell history:

read -rs KG_RAG_LIVE_KEY
KG_RAG_LIVE_URL=https://… KG_RAG_LIVE_KEY=$KG_RAG_LIVE_KEY python manage.py test tests.gateway.test_kg_rag_live
unset KG_RAG_LIVE_KEY

Each run sends one question: up to three LLM calls on the KG side. The RAG only reads the graph.
The Runpod proxy cuts a call at about 100 s, so a slow question (cold LLM worker) fails here with a
524, not a timeout. That is not a contract change, and the question still counts: wait several
minutes before running again.
"""
import os
from unittest import skipUnless

import httpx
from django.test import SimpleTestCase

from gateway.adapters.base import Result, ToolError
from gateway.adapters.kg_rag import NOT_ANSWERED, KgRagAdapter
from gateway.schemas import Envelope
from tests.gateway.support import load_fixture


@skipUnless(os.environ.get('KG_RAG_LIVE_URL') and os.environ.get('KG_RAG_LIVE_KEY'),
            'set KG_RAG_LIVE_URL and KG_RAG_LIVE_KEY to run the live KG RAG check')
class LiveKgRagContractTests(SimpleTestCase):
    def assert_same_shape(self, body, fixture_name):
        """The fixture's top-level keys are all there, with the same JSON types."""
        for name, value in load_fixture(fixture_name, 'kg_rag').items():
            with self.subTest(fixture=fixture_name, field=name):
                self.assertIn(name, body)
                self.assertIsInstance(body[name], type(value))

    def test_ask_matches_a_fixture_and_parses(self):
        base_url = os.environ['KG_RAG_LIVE_URL']
        key = os.environ['KG_RAG_LIVE_KEY']
        adapter = KgRagAdapter()
        outbound = adapter.build_request(None, 'ask', Envelope(input=load_fixture('ask_request.json', 'kg_rag')))
        response = httpx.post(base_url.rstrip('/') + outbound.path, json=outbound.json,
                              headers={'X-API-Key': key}, timeout=150)
        self.assertEqual(response.status_code, 200, response.text[:500])
        body = response.json()
        fixture = 'ask_200.json' if body.get('success') is True else 'ask_200_not_answered.json'
        self.assert_same_shape(body, fixture)
        parsed = adapter.parse_response(None, 'ask', 200, body)
        if isinstance(parsed, ToolError):
            self.assertEqual(parsed.message, NOT_ANSWERED)
        else:
            self.assertIsInstance(parsed, Result)
