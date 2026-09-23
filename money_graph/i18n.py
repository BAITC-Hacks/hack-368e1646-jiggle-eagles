"""Shared message keys; API/CLI text and reproducible exports stay in English."""
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent / 'static/locales/en.json').read_text(encoding='utf-8'))


def message(key: str, **params: object) -> dict:
    return {'key': key, 'params': params}


def render(part: dict) -> str:
    return CATALOG[part['key']].format(**part['params'])
