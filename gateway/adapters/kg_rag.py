"""The KG chatbot's RAG, as of KG repo commit a309fe5 (spec 2026-10-23-kg-rag-adapter-design.md)."""
from gateway.adapters.base import Adapter, Outbound
from gateway.errors import INVALID_REQUEST, GatewayError

ASK_PATH = '/ask'
INPUT_FIELDS = ('question', 'history')
# Limits count characters, not bytes.
MAX_QUESTION_CHARS = 4000
MAX_HISTORY_PAIRS = 20
MAX_HISTORY_ITEM_CHARS = 8000
NOT_ANSWERED = 'The tool could not answer the question.'


def refuse(message: str) -> GatewayError:
    return GatewayError(INVALID_REQUEST, message)


def check_text(name: str, value: str, limit: int) -> None:
    """Messages name the field, never its value."""
    if len(value) > limit:
        raise refuse(f'{name} is longer than {limit} characters.')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:  # a lone surrogate: httpx could not send it
        raise refuse(f'{name} is not valid text (it cannot be encoded as UTF-8).') from None


class KgRagAdapter(Adapter):
    operations = {'ask'}
    read_operations = frozenset()

    def build_request(self, tool, operation, envelope):
        if envelope.options:
            raise refuse(f'Unknown option(s) for ask: {", ".join(sorted(envelope.options))}. '
                         f'ask takes no options.')
        data = envelope.input
        unknown = sorted(set(data) - set(INPUT_FIELDS))
        if unknown:
            raise refuse(f'Unknown input field(s) for ask: {", ".join(unknown)}. '
                         f'Allowed: {", ".join(INPUT_FIELDS)}.')
        if 'question' not in data:
            raise refuse('input.question is required.')
        question = data['question']
        if not isinstance(question, str):
            raise refuse('input.question must be a string.')
        if not question.strip():
            raise refuse('input.question must not be empty.')
        check_text('input.question', question, MAX_QUESTION_CHARS)
        history = data.get('history', [])
        if not isinstance(history, list):
            raise refuse('input.history must be a list of [user_message, assistant_reply] pairs.')
        if len(history) > MAX_HISTORY_PAIRS:
            raise refuse(f'input.history has more than {MAX_HISTORY_PAIRS} pairs.')
        for i, pair in enumerate(history):
            if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(item, str) for item in pair)):
                raise refuse(f'input.history[{i}] must be a list of two strings.')
            for j, item in enumerate(pair):
                check_text(f'input.history[{i}][{j}]', item, MAX_HISTORY_ITEM_CHARS)
        return Outbound(method='POST', path=ASK_PATH,
                        json={'question': question, 'history': [list(pair) for pair in history]})
