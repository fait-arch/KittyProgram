"""Proveedores de IA intercambiables (AI_PROVIDER=deepseek | anthropic).

Interfaz única: complete(system, messages, schema) -> (texto, modelo). Si `schema` viene, el
texto devuelto es JSON (DeepSeek: modo JSON + esquema en el prompt; Claude: salida estructurada).
"""
import json
import logging
import os

import httpx

from ..core.config import get_settings
from ..core.errors import ApiError, unavailable

log = logging.getLogger(__name__)


def configured() -> bool:
    s = get_settings()
    if s.ai_provider == "deepseek":
        return bool(s.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY"))
    return bool(s.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def complete(system: str, messages: list[dict], schema: dict | None) -> tuple[str, str]:
    if not configured():
        s = get_settings()
        var = "DEEPSEEK_API_KEY" if s.ai_provider == "deepseek" else "ANTHROPIC_API_KEY"
        raise unavailable("ai_not_configured", f"Falta {var} en BACK/.env (AI_PROVIDER={s.ai_provider})")
    if get_settings().ai_provider == "deepseek":
        return _deepseek(system, messages, schema)
    return _anthropic(system, messages, schema)


# ── DeepSeek (API compatible con OpenAI) ──────────────────────────────
def _deepseek(system: str, messages: list[dict], schema: dict | None) -> tuple[str, str]:
    s = get_settings()
    sys_text = system
    body: dict = {"model": s.ai_model_name, "max_tokens": 8000, "stream": False}
    if schema:
        sys_text += ("\n\nResponde SOLO con un objeto json válido (sin texto alrededor) que cumpla "
                     f"exactamente este JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}")
        body["response_format"] = {"type": "json_object"}
    body["messages"] = [{"role": "system", "content": sys_text}, *messages]
    key = s.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    try:
        r = httpx.post(f"{s.deepseek_base_url.rstrip('/')}/chat/completions", json=body, timeout=120,
                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    except httpx.HTTPError as e:
        raise ApiError(502, "ai_unreachable", f"No se pudo conectar con DeepSeek: {type(e).__name__}")
    if r.status_code == 401:
        raise unavailable("ai_not_configured", "DEEPSEEK_API_KEY inválida")
    if r.status_code == 402:
        raise ApiError(502, "ai_no_balance", "La cuenta de DeepSeek no tiene saldo")
    if r.status_code == 429:
        raise ApiError(429, "ai_rate_limited", "Límite de uso de la IA alcanzado; reintentar en un minuto")
    if r.status_code >= 400:
        log.error("DeepSeek %s: %s", r.status_code, r.text[:500])
        raise ApiError(502, "ai_error", f"La IA respondió con error {r.status_code}")
    data = r.json()
    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ApiError(502, "ai_truncated", "La respuesta de la IA se cortó")
    if choice.get("finish_reason") == "content_filter":
        raise ApiError(502, "ai_refused", "La IA no pudo responder esta solicitud")
    return (choice["message"].get("content") or ""), data.get("model", s.ai_model_name)


# ── Claude (Anthropic) ────────────────────────────────────────────────
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _anthropic_client():
    import anthropic
    s = get_settings()
    return anthropic.Anthropic(api_key=s.anthropic_api_key or None, max_retries=2, timeout=120)


def _anthropic(system: str, messages: list[dict], schema: dict | None) -> tuple[str, str]:
    import anthropic
    s = get_settings()
    output_config: dict = {"effort": s.ai_effort}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    kwargs = dict(model=s.ai_model_name, max_tokens=16000,
                  system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                  messages=messages, output_config=output_config)
    client = _anthropic_client()
    try:
        try:
            msg = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
        except anthropic.BadRequestError as e:
            if "fallback" not in str(e).lower():
                raise
            msg = client.beta.messages.create(**kwargs)
    except anthropic.AuthenticationError:
        raise unavailable("ai_not_configured", "ANTHROPIC_API_KEY inválida")
    except anthropic.RateLimitError:
        raise ApiError(429, "ai_rate_limited", "Límite de uso de la IA alcanzado; reintentar en un minuto")
    except anthropic.APIStatusError as e:
        log.error("Claude API %s: %s", e.status_code, e.message)
        raise ApiError(502, "ai_error", f"La IA respondió con error {e.status_code}")
    except anthropic.APIConnectionError:
        raise ApiError(502, "ai_unreachable", "No se pudo conectar con la IA")
    if msg.stop_reason == "refusal":
        raise ApiError(502, "ai_refused", "La IA no pudo responder esta solicitud")
    if msg.stop_reason == "max_tokens":
        raise ApiError(502, "ai_truncated", "La respuesta de la IA se cortó")
    return "".join(b.text for b in msg.content if b.type == "text"), msg.model
