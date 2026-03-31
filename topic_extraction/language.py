from langdetect import detect, LangDetectException


def detect_language(text: str, comments: list[str] | None = None, fallback: str = 'en') -> str:
    """Detect the language of article text + first 3 comments.

    Args:
        text: Article or main text.
        comments: Optional list of comment strings. Only the first 3 are used.
        fallback: Language code to return if detection fails.

    Returns:
        ISO 639-1 language code (e.g. 'el', 'en', 'fr').
    """
    sample = text
    if comments:
        sample = text + ' ' + ' '.join(comments[:3])
    try:
        return detect(sample)
    except LangDetectException:
        return fallback
