from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from Src.infrastructure.ocr import gemini_pdf


# ════════════════════════════════════════════════════════════════════════════
# _to_float
# ════════════════════════════════════════════════════════════════════════════

class TestToFloat:
    def test_none_vira_zero(self):
        assert gemini_pdf._to_float(None) == 0.0

    def test_int(self):
        assert gemini_pdf._to_float(123) == 123.0

    def test_float(self):
        assert gemini_pdf._to_float(1.5) == 1.5

    def test_string_brl(self):
        assert gemini_pdf._to_float("R$ 1.234,56") == 1234.56

    def test_string_com_virgula(self):
        assert gemini_pdf._to_float("1234,56") == 1234.56

    def test_string_invalida(self):
        assert gemini_pdf._to_float("abc") == 0.0


# ════════════════════════════════════════════════════════════════════════════
# _normalize
# ════════════════════════════════════════════════════════════════════════════

class TestNormalize:
    def test_payload_minimo_aplica_defaults(self):
        r = gemini_pdf._normalize({})
        assert r["tipo"] == "NF-e"
        assert r["numero"] == "N/A"
        assert r["valor_total"] == 0.0
        assert r["icms"] == 0.0
        assert r["fonte"] == "GEMINI"

    def test_payload_completo(self):
        r = gemini_pdf._normalize({
            "tipo": "CT-e", "numero": "789",
            "valor_total": 5000.0, "icms": 350.0, "icms_taxa": 0.07,
            "pis": 82.5, "cofins": 380.0,
            "volume_total": 200.0, "volume": 200,
        })
        assert r["tipo"] == "CT-e"
        assert r["numero"] == "789"
        assert r["valor_total"] == 5000.0
        assert r["icms_taxa"] == pytest.approx(0.07)
        assert r["volume"] == 200

    def test_icms_taxa_em_percentual_convertida_para_decimal(self):
        # 12 (presumido %) > 1.0 → divide por 100
        r = gemini_pdf._normalize({"icms_taxa": 12.0, "valor_total": 1000, "icms": 120})
        assert r["icms_taxa"] == pytest.approx(0.12)

    def test_icms_taxa_derivada_quando_zero(self):
        # taxa=0, mas tem valor e icms → deriva
        r = gemini_pdf._normalize({"icms_taxa": 0, "valor_total": 1000, "icms": 200})
        assert r["icms_taxa"] == pytest.approx(0.2)

    def test_icms_taxa_limitada_a_30_pct(self):
        # Mesmo que venha 0.5 (50%), o clamp limita a 0.30
        r = gemini_pdf._normalize({"icms_taxa": 0.5})
        assert r["icms_taxa"] == 0.30

    def test_icms_taxa_negativa_vira_zero(self):
        r = gemini_pdf._normalize({"icms_taxa": -0.1})
        assert r["icms_taxa"] == 0.0

    def test_volume_convertido_para_int(self):
        r = gemini_pdf._normalize({"volume": 200.7})
        assert r["volume"] == 200
        assert isinstance(r["volume"], int)


# ════════════════════════════════════════════════════════════════════════════
# _extract_retry_seconds
# ════════════════════════════════════════════════════════════════════════════

class TestExtractRetrySeconds:
    def test_padrao_please_retry(self):
        assert gemini_pdf._extract_retry_seconds("Please retry in 31.5s.") == pytest.approx(31.5)

    def test_padrao_retry_delay(self):
        assert gemini_pdf._extract_retry_seconds("retryDelay: '45s'") == pytest.approx(45.0)

    def test_minimo_1s(self):
        assert gemini_pdf._extract_retry_seconds("retry in 0.1s") == 1.0

    def test_sem_padrao_retorna_60(self):
        assert gemini_pdf._extract_retry_seconds("qualquer erro") == 60.0


# ════════════════════════════════════════════════════════════════════════════
# _get_models
# ════════════════════════════════════════════════════════════════════════════

class TestGetModels:
    def test_default_inclui_fallbacks(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODELS", raising=False)
        monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash-lite,gemini-2.0-flash")
        modelos = gemini_pdf._get_models()
        assert gemini_pdf.DEFAULT_MODEL in modelos or modelos
        assert "gemini-2.0-flash-lite" in modelos

    def test_modelos_configurados_via_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")
        monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
        modelos = gemini_pdf._get_models()
        assert modelos[:2] == ["model-a", "model-b"]

    def test_nao_duplica_modelos_repetidos(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODELS", "modelo-x")
        monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "modelo-x,modelo-y")
        modelos = gemini_pdf._get_models()
        assert modelos.count("modelo-x") == 1
        assert "modelo-y" in modelos


# ════════════════════════════════════════════════════════════════════════════
# is_gemini_enabled
# ════════════════════════════════════════════════════════════════════════════

class TestIsGeminiEnabled:
    def test_sem_sdk(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake")
        monkeypatch.setattr(gemini_pdf, "genai", None)
        monkeypatch.setattr(gemini_pdf, "_GEMINI_BLOCKED_UNTIL", 0.0)
        assert gemini_pdf.is_gemini_enabled() is False

    def test_sem_chave(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setattr(gemini_pdf, "genai", MagicMock())
        monkeypatch.setattr(gemini_pdf, "_GEMINI_BLOCKED_UNTIL", 0.0)
        assert gemini_pdf.is_gemini_enabled() is False

    def test_com_sdk_e_chave(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        monkeypatch.setattr(gemini_pdf, "genai", MagicMock())
        monkeypatch.setattr(gemini_pdf, "_GEMINI_BLOCKED_UNTIL", 0.0)
        assert gemini_pdf.is_gemini_enabled() is True

    def test_bloqueado_temporariamente(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        monkeypatch.setattr(gemini_pdf, "genai", MagicMock())
        monkeypatch.setattr(gemini_pdf, "_GEMINI_BLOCKED_UNTIL", time.time() + 300)
        assert gemini_pdf.is_gemini_enabled() is False


# ════════════════════════════════════════════════════════════════════════════
# parse_pdf_with_gemini
# ════════════════════════════════════════════════════════════════════════════

class TestParsePdfWithGemini:
    def test_indisponivel_retorna_erro(self, monkeypatch, tmp_path):
        monkeypatch.setattr(gemini_pdf, "genai", None)
        r = gemini_pdf.parse_pdf_with_gemini(tmp_path / "x.pdf")
        assert "erro" in r
        assert "indispon" in r["erro"].lower()

    def test_resposta_valida_normalizada(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake")
        monkeypatch.setenv("GEMINI_MODELS", "modelo-teste")
        monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
        monkeypatch.setattr(gemini_pdf, "_GEMINI_BLOCKED_UNTIL", 0.0)

        fake_genai = MagicMock()
        fake_client = MagicMock()
        fake_genai.Client.return_value = fake_client
        fake_response = MagicMock()
        fake_response.text = '{"tipo":"NF-e","numero":"123","valor_total":1000,"icms":120,"icms_taxa":0.12,"pis":16.5,"cofins":76,"volume_total":10,"volume":10}'
        fake_client.models.generate_content.return_value = fake_response
        monkeypatch.setattr(gemini_pdf, "genai", fake_genai)
        monkeypatch.setattr(gemini_pdf, "types", MagicMock())

        r = gemini_pdf.parse_pdf_with_gemini(tmp_path / "x.pdf")
        assert r["numero"] == "123"
        assert r["valor_total"] == 1000.0
        assert r["fonte"] == "GEMINI"
        assert r["modelo"] == "modelo-teste"

    def test_resposta_vazia_falha(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake")
        monkeypatch.setenv("GEMINI_MODELS", "modelo-teste")
        monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
        monkeypatch.setattr(gemini_pdf, "_GEMINI_BLOCKED_UNTIL", 0.0)

        fake_genai = MagicMock()
        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.text = ""
        fake_client.models.generate_content.return_value = fake_response
        fake_genai.Client.return_value = fake_client
        monkeypatch.setattr(gemini_pdf, "genai", fake_genai)
        monkeypatch.setattr(gemini_pdf, "types", MagicMock())

        r = gemini_pdf.parse_pdf_with_gemini(tmp_path / "x.pdf")
        assert "erro" in r

    def test_quota_exceeded_bloqueia_temporariamente(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake")
        monkeypatch.setenv("GEMINI_MODELS", "m1")
        monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
        monkeypatch.setattr(gemini_pdf, "_GEMINI_BLOCKED_UNTIL", 0.0)

        fake_genai = MagicMock()
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = RuntimeError(
            "RESOURCE_EXHAUSTED: Please retry in 30s."
        )
        fake_genai.Client.return_value = fake_client
        monkeypatch.setattr(gemini_pdf, "genai", fake_genai)
        monkeypatch.setattr(gemini_pdf, "types", MagicMock())

        antes = time.time()
        r = gemini_pdf.parse_pdf_with_gemini(tmp_path / "x.pdf")
        assert "erro" in r
        # _GEMINI_BLOCKED_UNTIL deve ter sido aumentado
        assert gemini_pdf._GEMINI_BLOCKED_UNTIL > antes
