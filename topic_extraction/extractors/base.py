from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TopicResult:
    label: str
    score: float
    raw_score: float | None = None


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, article: str, comments: list[str], language: str = 'en') -> list[TopicResult]:
        """Extract topics from an article and its comments.

        Args:
            article: Main article text.
            comments: List of comment strings (flat, threading already resolved).
            language: ISO 639-1 language code of the input text.

        Returns:
            List of TopicResult sorted by score descending.
        """
