import re

# Pre-compiled patterns for performance (compiled once at module load)
_RE_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_RE_PAGE_MARKERS = re.compile(
    r'\b(?:page\s*\d+\s*(?:of\s*\d+)?)\b', re.IGNORECASE
)
_RE_LONG_DIGIT_NOISE = re.compile(r'\b\d{15,}\b')
_RE_MULTI_WHITESPACE = re.compile(r'[ \t]+')
_RE_BLANK_LINES = re.compile(r'\n{3,}')


def clean_text(text: str, max_tokens: int = 1500) -> str:
    """Clean extracted resume text while preserving phones, emails, and URLs.

    Args:
        text: Raw text extracted from a resume file.
        max_tokens: Maximum word count to keep (controls LLM context size).

    Returns:
        Cleaned text ready for LLM inference.
    """
    # 1. Strip ASCII control characters (keep newlines, tabs, spaces)
    text = _RE_CONTROL_CHARS.sub('', text)

    # 2. Remove page markers like "Page 1 of 3"
    text = _RE_PAGE_MARKERS.sub('', text)

    # 3. Remove only very long digit strings (15+ digits) that are noise,
    #    NOT phone numbers (which are 7-14 digits with separators)
    text = _RE_LONG_DIGIT_NOISE.sub('', text)

    # 4. Normalise whitespace: collapse runs of spaces/tabs, limit blank lines
    text = _RE_MULTI_WHITESPACE.sub(' ', text)
    text = _RE_BLANK_LINES.sub('\n\n', text)
    text = text.strip()

    # 5. Truncate to max_tokens words (preserves all contact info in header)
    words = text.split()
    if len(words) > max_tokens:
        text = ' '.join(words[:max_tokens])

    return text