import logging

from django.conf import settings
from langdetect import detect, LangDetectException


logger = logging.getLogger(__name__)


def detect_language(
    text: str,
    comments: list[str] | None = None,
    explicit: str | None = None,
) -> tuple[str, str]:
    """Resolve the language of the input. Returns (language_code, source).

    Resolution rules, in order:
      1. explicit provided AND in TOPIC_LANGUAGES   → ("<explicit>", "explicit")
      2. explicit provided but NOT in TOPIC_LANGUAGES → ValueError (caller turns this into 400)
      3. text long enough AND langdetect succeeds AND result in TOPIC_LANGUAGES
                                                     → ("<detected>", "detected")
      4. text long enough AND langdetect succeeds but result NOT in TOPIC_LANGUAGES
                                                     → (DEFAULT_LANGUAGE, "default"), logs warning
      5. otherwise (short text, langdetect raises)   → (DEFAULT_LANGUAGE, "default")
    """
    supported = list(settings.TOPIC_LANGUAGES)
    default = settings.DEFAULT_LANGUAGE
    min_chars = settings.LANG_DETECT_MIN_CHARS

    if explicit is not None:
        if explicit in supported:
            return explicit, 'explicit'
        raise ValueError(f'Unsupported language: {explicit!r}. Supported: {supported}')

    sample = text
    if comments:
        sample = text + ' ' + ' '.join(comments[:3])

    if len(sample) < min_chars:
        return default, 'default'

    try:
        detected = detect(sample)
    except LangDetectException:
        return default, 'default'

    if detected in supported:
        return detected, 'detected'

    logger.warning(
        'Unsupported language detected: %s (sample length %d). Falling back to %s.',
        detected, len(sample), default,
    )
    return default, 'default'
