"""PII scrubbing for text fields before external egress.

Built for the corpus refinement workflow but not currently wired in — the
corpus_pass command runs fully locally so no egress occurs. Wire scrub_text
into OpengovIngestor.load() (or whichever ingestor feeds external services)
when that changes.

Patterns are conservative: prefer leaving legislative text untouched over
over-scrubbing. Person-name NER is intentionally out of scope here.
"""
import re


_EMAIL_RE = re.compile(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_PHONE_INTL_RE = re.compile(r'\+30\s*\d{10}')
_PHONE_LOCAL_RE = re.compile(r'\b[26]\d{9}\b')
_AFM_RE = re.compile(r'(?i:ΑΦΜ)[\s:]*\d{9}')
_IBAN_COMPACT_RE = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b')
_IBAN_SPACED_RE = re.compile(
    r'\b[A-Z]{2}\d{2}(?:\s[A-Z0-9]{4}){2,7}(?:\s[A-Z0-9]{1,3})?\b'
)


def scrub_text(text: str) -> str:
    """Replace emails, Greek phones, ΑΦΜ, and IBANs with placeholder tokens."""
    if text is None:
        raise TypeError('scrub_text expects a string, got None')
    text = _IBAN_SPACED_RE.sub('[IBAN]', text)
    text = _IBAN_COMPACT_RE.sub('[IBAN]', text)
    text = _AFM_RE.sub('[AFM]', text)
    text = _EMAIL_RE.sub('[EMAIL]', text)
    text = _PHONE_INTL_RE.sub('[PHONE]', text)
    text = _PHONE_LOCAL_RE.sub('[PHONE]', text)
    return text
