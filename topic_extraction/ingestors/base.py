from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Conversation:
    article_id: str
    platform: str
    article: str
    comments: list[str] = field(default_factory=list)


class BaseIngestor(ABC):
    @abstractmethod
    def load(self, source) -> list[Conversation]:
        """Load conversations from a source.

        Args:
            source: File path, URL, or other source identifier (ingestor-specific).

        Returns:
            List of Conversation objects with threading flattened.
        """
