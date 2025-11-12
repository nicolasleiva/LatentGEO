# utils.py
from datetime import datetime
import json
import os


def now_iso():
    return datetime.utcnow().isoformat()


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
