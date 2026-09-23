"""Small strict JSON contracts, shared by tools, HTTP and model output validation."""
import hashlib
import json
import math
import re

VERSION = 1


class ReviewError(ValueError):
    def __init__(self, code: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(code)


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def digest(value: object) -> str:
    return hashlib.sha256(encode(value)).hexdigest()


def parse(body: str | bytes) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReviewError('invalid_json')
            result[key] = value
        return result
    def constant(_):
        raise ReviewError('invalid_json')
    def decimal(raw):
        value = float(raw)
        if not math.isfinite(value):
            raise ReviewError('invalid_json')
        return value
    try:
        return json.loads(body, object_pairs_hook=pairs, parse_constant=constant, parse_float=decimal)
    except (ValueError, TypeError, UnicodeError) as error:
        raise ReviewError('invalid_json') from error


def obj(**properties: dict) -> dict:
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


TEXT = dict(type='string', minLength=1, maxLength=1200)
ID = dict(type='string', pattern=r'^-?(0|[1-9][0-9]{0,18})$')
HASH = dict(type='string', pattern=r'^[0-9a-f]{64}$')
OFFSET = dict(type='integer', minimum=0, maximum=1000000)
LIMIT = dict(type='integer', minimum=1, maximum=100)


def validate(value: object, schema: dict) -> None:
    """Validate the deliberately small JSON Schema subset used in this package."""
    kind = schema['type']
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'integer': type(value) is int,
             'number': type(value) is int or type(value) is float and math.isfinite(value),
             'boolean': type(value) is bool, 'null': value is None}
    if not valid.get(kind, False) or ('enum' in schema and value not in schema['enum']):
        raise ReviewError('invalid_contract')
    if kind == 'object':
        if set(value) != set(schema['properties']):
            raise ReviewError('invalid_contract')
        for key, child in value.items():
            validate(child, schema['properties'][key])
    elif kind == 'array':
        if not schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 1000000):
            raise ReviewError('invalid_contract')
        for child in value:
            validate(child, schema['items'])
    elif kind == 'string':
        if not schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', 1000000):
            raise ReviewError('invalid_contract')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'], value):
            raise ReviewError('invalid_contract')
        try:
            value.encode('utf-8')
        except UnicodeError as error:
            raise ReviewError('invalid_contract') from error
    elif kind in ('integer', 'number'):
        if not schema.get('minimum', -math.inf) <= value <= schema.get('maximum', math.inf):
            raise ReviewError('invalid_contract')


FINDING = obj(evidence_id=HASH, measurement=TEXT, value={'type': 'number'}, unit=TEXT)
DECISION = obj(candidate_id=HASH, disposition={'type': 'string', 'enum': ['investigate', 'insufficient_evidence']},
    title=dict(TEXT, maxLength=160), reason=TEXT, next_step=TEXT,
    findings=dict(type='array', items=FINDING, minItems=1, maxItems=12),
    graph_selection=dict(type='array', items=ID, minItems=1, maxItems=50))
FINAL = obj(decisions=dict(type='array', items=DECISION, maxItems=12))
