from gateway.adapters.base import Adapter
from gateway.adapters.kg_rag import KgRagAdapter
from gateway.adapters.native import NativeAdapter
from gateway.adapters.topic_toolkit import TopicToolkitAdapter

# The only place adapters are registered. Tool.adapter must be one of these keys.
ADAPTERS: dict[str, Adapter] = {
    'kg_rag': KgRagAdapter(),
    'native': NativeAdapter(),
    'topic_toolkit': TopicToolkitAdapter(),
}
