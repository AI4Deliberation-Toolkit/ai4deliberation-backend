from django.test import SimpleTestCase
from pydantic import ValidationError

from gateway.adapters import ADAPTERS
from gateway.adapters.base import Outbound, Result, ToolError
from gateway.adapters.native import NativeAdapter
from gateway.adapters.topic_toolkit import TopicToolkitAdapter
from gateway.errors import GatewayError
from gateway.schemas import Envelope
from tests.gateway.support import load_fixture

TOOL = None  # adapters don't read the tool in v0


class RegistryTests(SimpleTestCase):
    def test_adapters_are_registered_by_key(self):
        self.assertEqual(sorted(ADAPTERS), ['native', 'topic_toolkit'])
        self.assertIsInstance(ADAPTERS['native'], NativeAdapter)
        self.assertIsInstance(ADAPTERS['topic_toolkit'], TopicToolkitAdapter)


class NativeAdapterTests(SimpleTestCase):
    adapter = NativeAdapter()

    def test_accepts_any_operation(self):
        self.assertIsNone(self.adapter.operations)

    def test_reads_are_declared_per_tool(self):
        self.assertIsNone(self.adapter.read_operations)

    def test_build_read_gets_the_operation_with_the_query(self):
        self.assertEqual(self.adapter.build_read_request(TOOL, 'query', {'a': '1', 'b': 'two words'}),
                         Outbound(method='GET', path='/query', params={'a': '1', 'b': 'two words'}, json=None))

    def test_build_posts_the_whole_envelope_to_the_operation(self):
        envelope = Envelope(input={'echo': 'hi'}, options={'x': 1}, session_id='s-1')
        self.assertEqual(
            self.adapter.build_request(TOOL, 'echo', envelope),
            Outbound(method='POST', path='/echo', params={},
                     json={'input': {'echo': 'hi'}, 'options': {'x': 1}, 'session_id': 's-1'}),
        )

    def test_parse_success(self):
        result = self.adapter.parse_response(TOOL, 'echo', 200, {'output': {'echo': 'hi'}, 'metadata': {'model_id': 'm'}})
        self.assertEqual(result, Result(output={'echo': 'hi'}, metadata={'model_id': 'm'}))

    def test_parse_success_without_metadata(self):
        self.assertEqual(self.adapter.parse_response(TOOL, 'echo', 201, {'output': {}}).metadata, {})

    def test_null_metadata_is_empty(self):
        self.assertEqual(self.adapter.parse_response(TOOL, 'echo', 200, {'output': {}, 'metadata': None}).metadata, {})

    def test_success_body_must_be_an_object_with_an_output_object(self):
        bodies = (None, [], 'text', {'result': {}}, {'output': 'text'},
                  {'output': {}, 'metadata': []}, {'output': {}, 'metadata': ''},
                  {'output': {}, 'metadata': 0}, {'output': {}, 'metadata': False})
        for body in bodies:
            with self.subTest(body=body):
                with self.assertRaises(GatewayError) as caught:
                    self.adapter.parse_response(TOOL, 'echo', 200, body)
                self.assertEqual(caught.exception.code, 'TOOL_BAD_RESPONSE')

    def test_error_status_raises_tool_error(self):
        with self.assertRaises(ToolError) as caught:
            self.adapter.parse_response(TOOL, 'echo', 422, {'detail': 'bad input'})
        self.assertEqual((caught.exception.status, caught.exception.body), (422, {'detail': 'bad input'}))

    def test_tool_error_str_never_includes_the_body(self):
        error = ToolError(500, {'detail': 'secret content'})
        self.assertNotIn('secret content', str(error))
        self.assertNotIn('secret content', repr(error))


class TopicToolkitAdapterTests(SimpleTestCase):
    adapter = TopicToolkitAdapter()

    def envelope(self, **options):
        return Envelope(input=load_fixture('extract_request.json'), options=options)

    def test_operations(self):
        self.assertEqual(self.adapter.operations, {'extract'})

    def test_build_sends_input_as_is(self):
        outbound = self.adapter.build_request(TOOL, 'extract', self.envelope())
        self.assertEqual(outbound, Outbound(method='POST', path='/api/topics/extract-conversation', params={},
                                            json=load_fixture('extract_request.json')))
        self.assertEqual(TopicToolkitAdapter().build_request(TOOL, 'extract', self.envelope()).method, 'POST')

    def test_options_become_query_parameters(self):
        outbound = self.adapter.build_request(TOOL, 'extract', self.envelope(include_labels=True, include_raw=True))
        self.assertEqual(outbound.params, {'include_labels': 'true', 'include_raw': 'true'})

    def test_false_options_are_omitted(self):
        outbound = self.adapter.build_request(TOOL, 'extract', self.envelope(include_labels=False))
        self.assertEqual(outbound.params, {})

    def test_unknown_option_is_rejected(self):
        with self.assertRaises(GatewayError) as caught:
            self.adapter.build_request(TOOL, 'extract', self.envelope(colour=True))
        self.assertEqual(caught.exception.code, 'INVALID_REQUEST')
        self.assertIn('colour', caught.exception.message)

    def test_option_must_be_boolean(self):
        for value in ('true', 1, None, {}):
            with self.subTest(value=value):
                with self.assertRaises(GatewayError) as caught:
                    self.adapter.build_request(TOOL, 'extract', self.envelope(include_labels=value))
                self.assertEqual(caught.exception.code, 'INVALID_REQUEST')
                self.assertIn('include_labels', caught.exception.message)

    def test_parse_201(self):
        body = load_fixture('extract_201.json')
        result = self.adapter.parse_response(TOOL, 'extract', 201, body)
        self.assertEqual(result.output, body)
        self.assertEqual(result.metadata, {'taxonomy_version': '2026-05-21-1'})

    def test_parse_201_with_labels(self):
        body = load_fixture('extract_201_labels.json')
        self.assertEqual(self.adapter.parse_response(TOOL, 'extract', 201, body).output, body)

    def test_backend_is_not_reported_as_a_model_id(self):
        result = self.adapter.parse_response(TOOL, 'extract', 201, load_fixture('extract_201.json'))
        self.assertNotIn('model_id', result.metadata)
        self.assertNotIn('tool_version', result.metadata)

    def test_missing_taxonomy_version_gives_empty_metadata(self):
        body = {k: v for k, v in load_fixture('extract_201.json').items() if k != 'taxonomy_version'}
        self.assertEqual(self.adapter.parse_response(TOOL, 'extract', 201, body).metadata, {})

    def test_success_body_must_be_an_object(self):
        for body in (None, [], 'text', 3):
            with self.subTest(body=body):
                with self.assertRaises(GatewayError) as caught:
                    self.adapter.parse_response(TOOL, 'extract', 201, body)
                self.assertEqual(caught.exception.code, 'TOOL_BAD_RESPONSE')

    def test_400_and_500_raise_tool_error_with_the_body(self):
        for status, name in ((400, 'extract_400.json'), (500, 'extract_500.json')):
            with self.subTest(status=status):
                with self.assertRaises(ToolError) as caught:
                    self.adapter.parse_response(TOOL, 'extract', status, load_fixture(name))
                self.assertEqual((caught.exception.status, caught.exception.body), (status, load_fixture(name)))


class EnvelopeTests(SimpleTestCase):
    def test_defaults(self):
        envelope = Envelope(input={})
        self.assertEqual((envelope.options, envelope.session_id), ({}, None))

    def test_unknown_top_level_keys_are_rejected(self):
        with self.assertRaises(ValidationError):
            Envelope(input={}, inputs={})
