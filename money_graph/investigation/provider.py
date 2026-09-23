"""Backend-only Responses transport; no retries that could duplicate paid requests."""
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .contracts import ReviewError, encode, parse

DEFAULT_MODEL = 'gpt-5.4-2026-03-05'
MODEL_PRICES = {
    DEFAULT_MODEL: (2.50, 15.00), 'gpt-5.4': (2.50, 15.00),
    'gpt-5.4-mini-2026-03-17': (0.75, 4.50), 'gpt-5.4-mini': (0.75, 4.50),
}


@dataclass(frozen=True)
class AISettings:
    api_key: str = field(default='', repr=False)
    model: str = DEFAULT_MODEL
    input_price: float = 2.50
    output_price: float = 15.00
    max_usd: float = 0.75

    @classmethod
    def from_env(cls):
        # Read only documented settings; never execute shell content in a local .env.
        values = {}
        path = Path('.env')
        if path.is_file():
            for line in path.read_text().splitlines():
                key, separator, value = line.partition('=')
                if separator and (key.strip().startswith('MONEY_GRAPH_AI_') or key.strip() in {'OPENAI_API_KEY', 'OPENAI_MODEL'}):
                    values[key.strip()] = value.strip().strip('"\'')
        values.update(os.environ)
        model = values.get('OPENAI_MODEL') or DEFAULT_MODEL
        input_price, output_price = MODEL_PRICES.get(model, (math.nan, math.nan))
        try:
            settings = cls(api_key=values.get('OPENAI_API_KEY', ''), model=model,
                input_price=float(values.get('MONEY_GRAPH_AI_INPUT_USD_PER_MILLION') or input_price),
                output_price=float(values.get('MONEY_GRAPH_AI_OUTPUT_USD_PER_MILLION') or output_price),
                max_usd=float(values.get('MONEY_GRAPH_AI_MAX_USD') or 0.75))
            if any(not math.isfinite(v) or v <= 0 for v in (settings.input_price, settings.output_price, settings.max_usd)):
                raise ValueError('price')
            return settings
        except ValueError as error:
            raise ReviewError('ai_configuration', 503) from error

    def public(self):
        return dict(model=self.model, input_usd_per_million=self.input_price,
                    output_usd_per_million=self.output_price, max_usd=self.max_usd,
                    price_basis='Configured standard text-token rates; cached input charged conservatively at full input rate. Default rates verified 2026-09-23.')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReviewError('provider_redirect', 502)


class ResponsesProvider:
    def __init__(self, settings: AISettings):
        self.settings = settings

    def __call__(self, payload: dict, timeout: float) -> dict:
        if not self.settings.api_key:
            raise ReviewError('ai_disabled', 503)
        request = Request('https://api.openai.com/v1/responses', data=encode(payload), method='POST',
                          headers={'Authorization': 'Bearer ' + self.settings.api_key, 'Content-Type': 'application/json'})
        try:
            with build_opener(NoRedirect).open(request, timeout=timeout) as response:
                body = response.read(2 * 1024 * 1024 + 1)
                if len(body) > 2 * 1024 * 1024:
                    raise ReviewError('provider_response_limit', 502)
                value = parse(body)
                if not isinstance(value, dict):
                    raise ReviewError('provider_response', 502)
                return value
        except HTTPError as error:
            # Provider bodies can echo submitted content. Expose only safe categories.
            code = {401: 'provider_auth', 403: 'provider_auth', 429: 'provider_rate_limit'}.get(error.code, 'provider_error')
            raise ReviewError(code, 502) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ReviewError('provider_network', 502) from error
