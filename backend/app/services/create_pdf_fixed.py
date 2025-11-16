#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def clean_string_for_pdf(text):
    """Asegura que el string esté en formato amigable para PDF."""
    if not isinstance(text, str):
        text = str(text)
    # Reemplazar caracteres Unicode problemáticos
    replacements = {
        "•": "-",
        "–": "-",
        "—": "-",
        "'": "'",
        "'": "'",
        """: '"',
        """: '"',
        "…": "...",
        "→": "->",
        "←": "<-",
        "↑": "^",
        "↓": "v",
        "✓": "[OK]",
        "✗": "[X]",
        "★": "*",
        "©": "(c)",
        "®": "(R)",
        "™": "(TM)",
        "📚": "[LIBRO]",
        "📊": "[GRAFICO]",
        "📈": "[TENDENCIA]",
        "🔍": "[BUSCAR]",
        "✅": "[OK]",
        "❌": "[X]",
        "⚠️": "[ALERTA]",
        "💡": "[IDEA]",
        "🎯": "[OBJETIVO]",
        "🚀": "[COHETE]",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    import re
    text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
    
    return (
        text.replace("\r", "")
        .replace("\\r", "")
        .replace("\\n", "\n")
        .replace("\\t", "    ")
    )
