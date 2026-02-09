
import re

def clean_latin1(text):
    if not isinstance(text, str):
        return str(text)
    
    replacements = {
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "\u2013": "-", "\u2014": "-",
        "\u2265": ">=", "\u2264": "<=",
        "\u2026": "...",
        "\u2022": "-",
        "≥": ">=", "≤": "<=",
        "–": "-", "—": "-",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    
    try:
        text.encode('latin-1')
        return text
    except UnicodeEncodeError:
        return text.encode('latin-1', 'replace').decode('latin-1')

def clean_string_for_pdf(text):
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "•": "-", "–": "-", "—": "-", "…": "...",
        "→": "->", "←": "<-", "↑": "^", "↓": "v",
        "✓": "[OK]", "✗": "[X]", "★": "*",
        "©": "(c)", "®": "(R)", "™": "(TM)",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
    return text

print(f"Test clean_latin1('Índice'): '{clean_latin1('Índice')}'")
print(f"Test clean_string_for_pdf('Índice'): '{clean_string_for_pdf('Índice')}'")
