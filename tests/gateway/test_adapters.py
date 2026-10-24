from django.test import SimpleTestCase
from pydantic import ValidationError

from gateway.adapters import ADAPTERS
from gateway.adapters.base import Outbound, Result, ToolError
from gateway.adapters.kg_rag import KgRagAdapter
from gateway.adapters.native import NativeAdapter
from gateway.adapters.topic_toolkit import TopicToolkitAdapter
from gateway.errors import GatewayError
from gateway.schemas import Envelope
from tests.gateway.support import load_fixture

TOOL = None  # adapters don't read the tool in v0


class RegistryTests(SimpleTestCase):
    def test_adapters_are_registered_by_key(self):
        self.assertEqual(sorted(ADAPTERS), ['kg_rag', 'native', 'topic_toolkit'])
        self.assertIsInstance(ADAPTERS['kg_rag'], KgRagAdapter)
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
        self.assertEqual(self.adapter.operations, {'extract', 'taxonomy', 'article-topics', 'similar-articles'})

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


class TopicToolkitReadTests(SimpleTestCase):
    adapter = TopicToolkitAdapter()

    def build(self, operation, params):
        return self.adapter.build_read_request(TOOL, operation, params)

    def test_reads(self):
        self.assertEqual(self.adapter.read_operations, {'taxonomy', 'article-topics', 'similar-articles'})

    def test_taxonomy(self):
        self.assertEqual(self.build('taxonomy', {'language': 'el'}),
                         Outbound(method='GET', path='/api/topics', params={'language': 'el'}, json=None))
        self.assertEqual(self.build('taxonomy', {}).params, {})

    def test_empty_optional_value_is_forwarded(self):
        self.assertEqual(self.build('taxonomy', {'language': ''}).params, {'language': ''})

    def test_article_topics(self):
        outbound = self.build('article-topics', {'article_id': '42', 'include_labels': 'true', 'include_raw': 'false'})
        self.assertEqual((outbound.path, outbound.params), ('/api/topics/article/42', {'include_labels': 'true'}))

    def test_similar_articles(self):
        outbound = self.build('similar-articles', {'platform': 'wordpress-opengov', 'article_id': '42', 'k': '5',
                                                   'topic_slug': 'public_finance'})
        self.assertEqual((outbound.path, outbound.params),
                         ('/api/articles/wordpress-opengov/42/similar', {'k': '5', 'topic_slug': 'public_finance'}))

    def test_path_values_are_one_encoded_segment(self):  # spec §5.6; Review Focus 5
        cases = {'../x': '..%2Fx', 'a/b': 'a%2Fb', 'a?b#c': 'a%3Fb%23c', '%2F': '%252F',
                 'άρθρο': '%CE%AC%CF%81%CE%B8%CF%81%CE%BF', '...': '...'}
        for value, encoded in cases.items():
            with self.subTest(value=value):
                self.assertEqual(self.build('article-topics', {'article_id': value}).path,
                                 f'/api/topics/article/{encoded}')
        self.assertEqual(self.build('similar-articles', {'platform': 'a/b', 'article_id': '1'}).path,
                         '/api/articles/a%2Fb/1/similar')

    def test_dot_segments_and_empty_path_values_are_refused(self):
        for op, params, name in (('article-topics', {'article_id': ''}, 'article_id'),
                                 ('article-topics', {'article_id': '.'}, 'article_id'),
                                 ('article-topics', {'article_id': '..'}, 'article_id'),
                                 ('similar-articles', {'platform': '..', 'article_id': '1'}, 'platform')):
            with self.subTest(op=op, params=params):
                with self.assertRaises(GatewayError) as caught:
                    self.build(op, params)
                self.assertEqual(caught.exception.code, 'INVALID_REQUEST')
                self.assertIn(name, caught.exception.message)

    def test_unknown_parameter_names_the_allowed_ones(self):
        with self.assertRaises(GatewayError) as caught:
            self.build('taxonomy', {'lang': 'el'})
        self.assertIn('lang', caught.exception.message)
        self.assertIn('language', caught.exception.message)

    def test_missing_path_parameter(self):
        with self.assertRaises(GatewayError) as caught:
            self.build('similar-articles', {'article_id': '1'})
        self.assertIn('platform', caught.exception.message)

    def test_flags_are_true_or_false(self):
        with self.assertRaises(GatewayError) as caught:
            self.build('article-topics', {'article_id': '1', 'include_raw': 'yes'})
        self.assertIn('include_raw', caught.exception.message)

    def test_parse_reads(self):
        for op, name, metadata in (('taxonomy', 'taxonomy_200.json', {'taxonomy_version': '2026-05-21-1'}),
                                   ('article-topics', 'article_topics_200.json', {'taxonomy_version': '2026-05-21-1'}),
                                   ('similar-articles', 'similar_articles_200.json', {})):
            with self.subTest(op=op):
                result = self.adapter.parse_response(TOOL, op, 200, load_fixture(name))
                self.assertEqual((result.output, result.metadata), (load_fixture(name), metadata))

    def test_read_errors_raise_tool_error_with_the_body(self):
        for op, status, name in (('taxonomy', 400, 'taxonomy_400.json'),
                                 ('article-topics', 404, 'article_topics_404.json'),
                                 ('similar-articles', 400, 'similar_articles_400.json')):
            with self.subTest(op=op):
                with self.assertRaises(ToolError) as caught:
                    self.adapter.parse_response(TOOL, op, status, load_fixture(name))
                self.assertEqual((caught.exception.status, caught.exception.body), (status, load_fixture(name)))


class EnvelopeTests(SimpleTestCase):
    def test_defaults(self):
        envelope = Envelope(input={})
        self.assertEqual((envelope.options, envelope.session_id), ({}, None))

    def test_unknown_top_level_keys_are_rejected(self):
        with self.assertRaises(ValidationError):
            Envelope(input={}, inputs={})


SECRET = 'SECRET-VALUE-4b7e'
# Decision 2's messages, copied: the tests pin the exact text, so a case can't pass on the wrong check.
NOT_A_STRING = 'input.question must be a string.'
NOT_PAIRS = 'input.history must be a list of [user_message, assistant_reply] pairs.'
NOT_TEXT = '{} is not valid text (it cannot be encoded as UTF-8).'
UNKNOWN_WP = 'Unknown input field(s) for ask: wp_user_id. Allowed: question, history.'
NO_OPTIONS = 'Unknown option(s) for ask: stream. ask takes no options.'


class KgRagAdapterTests(SimpleTestCase):
    adapter = KgRagAdapter()

    def build(self, input, **options):
        return self.adapter.build_request(TOOL, 'ask', Envelope(input=input, options=options, session_id='s-1'))

    def assert_refused(self, input, message, **options):
        with self.assertRaises(GatewayError) as caught:
            self.build(input, **options)
        self.assertEqual(caught.exception.code, 'INVALID_REQUEST')
        self.assertEqual(caught.exception.message, message)
        self.assertNotIn(SECRET, caught.exception.message)

    def test_operations(self):
        self.assertEqual((self.adapter.operations, self.adapter.read_operations), ({'ask'}, frozenset()))

    def test_build_posts_question_and_history(self):  # Review Focus 5: blank pair kept
        history = [['Τι είναι;', 'Μια απάντηση.'], ['', '']]
        self.assertEqual(self.build({'question': '  Ποιο νομοσχέδιο; ', 'history': history}),
                         Outbound(method='POST', path='/ask', params={},
                                  json={'question': '  Ποιο νομοσχέδιο; ', 'history': history}))

    def test_history_defaults_to_empty_and_session_id_is_not_sent(self):
        self.assertEqual(self.build(load_fixture('ask_request.json', 'kg_rag')).json,
                         {**load_fixture('ask_request.json', 'kg_rag'), 'history': []})

    def test_limits_are_inclusive_and_count_characters(self):  # Review Focus 2
        outbound = self.build({'question': 'α' * 4000, 'history': [['β' * 8000, 'γ' * 8000]] * 20})
        self.assertEqual(len(outbound.json['history']), 20)
        self.assert_refused({'question': 'α' * 4001}, 'input.question is longer than 4000 characters.')
        self.assert_refused({'question': 'q', 'history': [['β' * 8001, 'b']]},
                            'input.history[0][0] is longer than 8000 characters.')

    def test_input_refusals_give_the_exact_message_and_no_value(self):
        q = {'question': 'q'}
        cases = [
            ({}, 'input.question is required.'),
            ({'question': None}, NOT_A_STRING), ({'question': 42}, NOT_A_STRING), ({'question': [SECRET]}, NOT_A_STRING),
            ({'question': ''}, 'input.question must not be empty.'),
            ({'question': ' \n\t '}, 'input.question must not be empty.'),
            ({'question': SECRET + 'x' * 4000}, 'input.question is longer than 4000 characters.'),
            ({'question': SECRET + '\ud800'}, NOT_TEXT.format('input.question')),
            ({**q, 'history': None}, NOT_PAIRS), ({**q, 'history': SECRET}, NOT_PAIRS),
            ({**q, 'history': {'a': SECRET}}, NOT_PAIRS),
            ({**q, 'history': [['a', 'b']] * 21}, 'input.history has more than 20 pairs.'),
            ({**q, 'history': [None]}, 'input.history[0] must be a list of two strings.'),
            ({**q, 'history': [[SECRET]]}, 'input.history[0] must be a list of two strings.'),
            ({**q, 'history': [[SECRET, 'b', 'c']]}, 'input.history[0] must be a list of two strings.'),
            ({**q, 'history': [{'user': SECRET, 'assistant': 'b'}]}, 'input.history[0] must be a list of two strings.'),
            ({**q, 'history': [['a', 'b'], [SECRET, None]]}, 'input.history[1] must be a list of two strings.'),
            ({**q, 'history': [[SECRET, 7]]}, 'input.history[0] must be a list of two strings.'),
            ({**q, 'history': [['a', SECRET + 'x' * 8000]]}, 'input.history[0][1] is longer than 8000 characters.'),
            ({**q, 'history': [[SECRET + '\udfff', 'b']]}, NOT_TEXT.format('input.history[0][0]')),
            ({**q, 'wp_user_id': SECRET}, UNKNOWN_WP),
            ({**q, 'username': SECRET}, 'Unknown input field(s) for ask: username. Allowed: question, history.'),
        ]
        for input, message in cases:
            with self.subTest(message=message, input=repr(input)[:60]):
                self.assert_refused(input, message)

    def test_unknown_input_keys_are_sorted_and_list_the_allowed_ones(self):
        self.assert_refused({'question': 'q', 'wp_user_id': SECRET, 'username': SECRET},
                            'Unknown input field(s) for ask: username, wp_user_id. Allowed: question, history.')

    def test_any_option_is_refused(self):
        self.assert_refused({'question': 'q'}, NO_OPTIONS, stream=True)

    def test_the_first_failing_check_is_reported(self):  # decision 1: options → unknown keys → question → history
        self.assert_refused({'wp_user_id': SECRET}, NO_OPTIONS, stream=True)
        self.assert_refused({'wp_user_id': SECRET, 'history': None}, UNKNOWN_WP)
        self.assert_refused({'question': '', 'history': None}, 'input.question must not be empty.')
