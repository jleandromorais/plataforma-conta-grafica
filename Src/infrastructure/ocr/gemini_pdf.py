from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None  # type: ignore
    types = None  # type: ignore


load_dotenv()


DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
_GEMINI_BLOCKED_UNTIL = 0.0


def _get_models() -> list[str]:
    """Lista de modelos para tentativa, em ordem de prioridade."""
    configured = os.getenv("GEMINI_MODELS", "").strip()
    if configured:
        models = [m.strip() for m in configured.split(",") if m.strip()]
    else:
        models = [DEFAULT_MODEL]

    # Fallbacks seguros no endpoint atual
    fallback_models = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash-lite,gemini-2.0-flash")
    for candidate in [m.strip() for m in fallback_models.split(",") if m.strip()]:
        if candidate not in models:
            models.append(candidate)

    return models


def _get_api_key() -> str:
    return (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()


def is_gemini_enabled() -> bool:
    """Retorna True quando há SDK + chave configurada."""
    global _GEMINI_BLOCKED_UNTIL
    key = _get_api_key()
    return bool(genai and key and time.time() >= _GEMINI_BLOCKED_UNTIL)


def _extract_retry_seconds(error_text: str) -> float:
    """Extrai tempo de retry sugerido em segundos de mensagens da API."""
    # Ex.: "Please retry in 31.581067215s."
    m = re.search(r"retry in\s+([\d.]+)s", error_text, flags=re.IGNORECASE)
    if m:
        try:
            return max(1.0, float(m.group(1)))
        except ValueError:
            pass

    # Ex.: "retryDelay': '31s'"
    m = re.search(r"retryDelay[^\d]*([\d.]+)s", error_text, flags=re.IGNORECASE)
    if m:
        try:
            return max(1.0, float(m.group(1)))
        except ValueError:
            pass

    # Backoff padrão conservador
    return 60.0


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    valor_total = _to_float(data.get("valor_total", 0.0))
    icms = _to_float(data.get("icms", 0.0))
    icms_taxa = _to_float(data.get("icms_taxa", 0.0))

    if icms_taxa > 1.0:
        icms_taxa = icms_taxa / 100.0

    if icms_taxa <= 0.0 and valor_total > 0 and icms > 0:
        icms_taxa = icms / valor_total

    return {
        "tipo": str(data.get("tipo", "NF-e")),
        "numero": str(data.get("numero", "N/A")),
        "valor_total": valor_total,
        "icms": icms,
        "icms_taxa": max(0.0, min(icms_taxa, 0.30)),
        "pis": _to_float(data.get("pis", 0.0)),
        "cofins": _to_float(data.get("cofins", 0.0)),
        "volume_total": _to_float(data.get("volume_total", 0.0)),
        "volume": int(_to_float(data.get("volume", 0))),
        "fonte": "GEMINI",
    }


def parse_pdf_with_gemini(pdf_path: Path) -> Dict[str, Any]:
    """Extrai campos fiscais com Gemini a partir do PDF original."""
    global _GEMINI_BLOCKED_UNTIL

    if not is_gemini_enabled():
        return {"erro": "Gemini indisponível (SDK/chave ausente)"}

    api_key = _get_api_key()
    model_names = _get_models()

    try:
        client = genai.Client(api_key=api_key)

        uploaded = client.files.upload(file=str(pdf_path))

        prompt = (
            "Voce e um extrator fiscal brasileiro. Leia o PDF e responda SOMENTE JSON valido. "
            "Nao use markdown. Campos obrigatorios: tipo, numero, valor_total, icms, icms_taxa, "
            "pis, cofins, volume_total, volume. "
            "Regras: tipo em 'NF-e' ou 'CT-e'; numero string; valores numericos; "
            "icms_taxa em decimal (12% => 0.12); se nao achar algum campo use 0."
        )

        errors: list[str] = []
        had_quota_error = False

        for model_name in model_names:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[uploaded, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                    ),
                )

                raw = (response.text or "").strip()
                if not raw:
                    errors.append(f"{model_name}: resposta vazia")
                    continue

                data = json.loads(raw)
                if not isinstance(data, dict):
                    errors.append(f"{model_name}: JSON inválido")
                    continue

                normalized = _normalize(data)
                normalized["modelo"] = model_name
                return normalized
            except Exception as e:
                err_text = str(e)
                errors.append(f"{model_name}: {err_text}")
                if "RESOURCE_EXHAUSTED" in err_text or "Quota exceeded" in err_text or "429" in err_text:
                    had_quota_error = True
                continue

        if had_quota_error:
            wait_s = _extract_retry_seconds("\n".join(errors))
            _GEMINI_BLOCKED_UNTIL = time.time() + wait_s

        return {"erro": f"Gemini falhou: {' | '.join(errors) if errors else 'sem resposta válida'}"}
    except Exception as e:  # pragma: no cover
        err_text = str(e)

        # Em estouro de cota/rate limit, bloqueia tentativas por alguns segundos.
        if "RESOURCE_EXHAUSTED" in err_text or "Quota exceeded" in err_text or "429" in err_text:
            wait_s = _extract_retry_seconds(err_text)
            _GEMINI_BLOCKED_UNTIL = time.time() + wait_s

        return {"erro": f"Gemini falhou: {err_text}"}
