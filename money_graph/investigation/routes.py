"""Thin same-origin HTTP adapter for the investigation service."""
import re

from .contracts import ReviewError, encode, parse

ROUTE = re.compile(r'/api/analyses/(startup|[0-9a-f]{32})/reviews(?:/([0-9a-f]{32})(?:/(cancel|follow-up|briefs|evidence|graph)(?:/([0-9a-f]{64}))?)?)?')


def handle_review(handler, method: str, path: str) -> bool:
    route = ROUTE.fullmatch(path)
    if route is None:
        return False
    analysis_id, review_id, action, reference = route.groups()
    service = handler.server.reviews
    try:
        if method == 'GET':
            if review_id is None:
                result = service.list(analysis_id)
            elif action is None:
                result = service.get(analysis_id, review_id)
            elif action == 'evidence' and reference:
                record = service.get(analysis_id, review_id)
                if reference not in record['evidence']:
                    raise ReviewError('evidence_missing', 404)
                result = record['evidence'][reference]
            elif action == 'graph' and reference:
                result = service.graph(analysis_id, review_id, reference)
            else:
                raise ReviewError('record_missing', 404)
            status = 200
        else:
            handler.close_connection = True
            lengths = handler.headers.get_all('Content-Length', [])
            if handler.headers.get('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isdigit():
                raise ReviewError('invalid_body')
            length = int(lengths[0])
            if not 0 < length <= 16384:
                raise ReviewError('body_limit', 413)
            if handler.headers.get_content_type() != 'application/json':
                raise ReviewError('body_type', 415)
            handler.connection.settimeout(10)
            raw = handler.rfile.read(length)
            if len(raw) != length:
                raise ReviewError('invalid_body')
            body = parse(raw)
            status = 200
            if review_id is None:
                result = service.start(analysis_id, body)
                status = 200 if result.get('reused') else 202
            elif action == 'cancel' and reference is None and body == {}:
                result = service.cancel(analysis_id, review_id)
            elif action == 'follow-up' and reference is None:
                result = service.follow_up(analysis_id, review_id, body)
            elif action == 'briefs' and reference is None:
                result = service.brief(analysis_id, review_id, body)
            else:
                raise ReviewError('invalid_body')
        handler.send(status, encode(result), 'application/json')
    except ReviewError as error:
        handler.send(error.status, encode(dict(error=error.code, error_code=error.code)), 'application/json')
    except OSError:
        handler.send(500, encode(dict(error='review_storage', error_code='review_storage')), 'application/json')
    return True
