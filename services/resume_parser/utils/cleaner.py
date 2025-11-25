import re
import os
import unicodedata
from langdetect import detect

# ============================================================================
# TEXT PREPROCESSING - From your existing code
# ============================================================================

# Precompile regex patterns
REGEX_CONTROL = re.compile(r'[\x00-\x1F\x7F]')
REGEX_ZERO_WIDTH = re.compile(r'[\u200b\u200c\u200d\uFEFF]')
REGEX_MOJIBAKE = re.compile(r'[ïŒ‚]')
REGEX_BROKEN_HYPHEN = re.compile(r'-\s*\n\s*')
REGEX_MULTI_SPACES = re.compile(r'\s{2,}')
REGEX_MULTI_NEWLINES = re.compile(r'\n{2,}')

MOJIBAKE_REPLACEMENTS = {
    'â€"': '-', 'â€"': '-', 'â€': '-',
    'â€™': "'", 'â€œ': '"', 'â€�': '"',
    'â€˜': "'", 'â€¢': '•', 'â€¦': '...',
    '\ufffd': '',
}


def clean_text(text: str) -> str:
    """Clean and normalize extracted text"""
    if not text:
        return ""
    
    # Normalize Unicode
    text = unicodedata.normalize('NFKD', text)
    
    # Fix mojibake
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    
    # Remove control characters
    text = REGEX_CONTROL.sub(' ', text)
    text = REGEX_ZERO_WIDTH.sub('', text)
    
    # Fix broken hyphenated line breaks
    text = REGEX_BROKEN_HYPHEN.sub('', text)
    
    # Remove mojibake noise
    text = REGEX_MOJIBAKE.sub(' ', text)
    
    # Normalize spacing
    text = REGEX_MULTI_SPACES.sub(' ', text)
    text = REGEX_MULTI_NEWLINES.sub('\n', text)
    
    # Keep only printable characters
    text = ''.join(ch for ch in text if ch.isprintable() or ch in '\n\t')
    
    return text.strip()



    