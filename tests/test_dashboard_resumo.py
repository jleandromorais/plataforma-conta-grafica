"""
QA — testes do PainelResumo (dashboard_resumo.py)

Cobertura:
  - Funções puras de formatação
  - _chave_periodo (ordenação cronológica)
  - _PERIODO_VALIDO (filtro de entradas inválidas)
  - _atualizar_cards: valor atual, variação MoM, sem dados, anterior zero
  - _filtrar_por_ano: todos, ano específico, sem resultado
  - _carregar_do_banco: integração com SQLite temporário
  - PainelResumo.__init__ com banco mockado (sem janela real)
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

# ── helpers isolados (não precisam de Tk) ─────────────────────────────────────
from Src.Views.dashboard_resumo import (
    TODOS_OS_ANOS,
    _PERIODO_VALIDO,
    _chave_periodo,
    _fmt_moeda,
    _fmt_moeda_compacta,
    _fmt_pct,
    _fmt_pmpv,
)


# ═══════════════════════════════════════════════════════════════════════
# 1. FORMATAÇÃO — funções puras, zero dependência externa
# ═══════════════════════════════════════════════════════════════════════

class TestFmtMoeda:
    def test_zero(self):
        assert _fmt_moeda(0) == "R$ 0,00"

    def test_inteiro(self):
        assert _fmt_moeda(1000) == "R$ 1.000,00"

    def test_decimal(self):
        assert _fmt_moeda(1234567.89) == "R$ 1.234.567,89"

    def test_negativo(self):
        assert _fmt_moeda(-500) == "R$ -500,00"

    def test_separadores_pt_br(self):
        resultado = _fmt_moeda(1_000_000)
        assert "." in resultado   # separador de milhar
        assert "," in resultado   # separador decimal
        assert resultado == "R$ 1.000.000,00"


class TestFmtMoedaCompacta:
    def test_abaixo_mil(self):
        assert _fmt_moeda_compacta(500) == "R$ 500,00"

    def test_mil(self):
        r = _fmt_moeda_compacta(1_500)
        assert "mil" in r
        assert "1,5" in r

    def test_milhao(self):
        r = _fmt_moeda_compacta(1_200_000)
        assert "Mi" in r
        assert "1,20" in r

    def test_negativo_milhao(self):
        r = _fmt_moeda_compacta(-2_000_000)
        assert r.startswith("-")
        assert "Mi" in r

    def test_zero(self):
        assert _fmt_moeda_compacta(0) == "R$ 0,00"


class TestFmtPmpv:
    def test_quatro_casas(self):
        r = _fmt_pmpv(1.9988)
        assert r.startswith("R$")
        # 4 casas decimais
        parte_decimal = r.split(",")[1]
        assert len(parte_decimal) == 4

    def test_zero(self):
        assert _fmt_pmpv(0) == "R$ 0,0000"


class TestFmtPct:
    def test_positivo(self):
        r = _fmt_pct(5.1)
        assert r.startswith("+")
        assert "5,1" in r

    def test_negativo(self):
        r = _fmt_pct(-10.5)
        assert r.startswith("-")
        assert "10,5" in r

    def test_zero(self):
        assert _fmt_pct(0) == "+0,0%"


# ═══════════════════════════════════════════════════════════════════════
# 2. VALIDAÇÃO E ORDENAÇÃO DE PERÍODOS
# ═══════════════════════════════════════════════════════════════════════

class TestPeriodoValido:
    @pytest.mark.parametrize("periodo", [
        "Jan/2026", "Fev/2025", "Dez/2024",
        "Mar/2026", "Abr/2026", "Mai/2026",
    ])
    def test_formato_valido(self, periodo):
        assert _PERIODO_VALIDO.match(periodo)

    @pytest.mark.parametrize("invalido", [
        "TESTE2", "leandro[", "DEZ 2025", "", "Jan26",
        "13/2026", "Jan/26", "Janeiro/2026",
    ])
    def test_formato_invalido(self, invalido):
        assert not _PERIODO_VALIDO.match(invalido)


class TestChavePeriodo:
    def test_ordem_basica(self):
        assert _chave_periodo("Jan/2026") < _chave_periodo("Fev/2026")
        assert _chave_periodo("Dez/2025") < _chave_periodo("Jan/2026")

    def test_mesmo_mes_anos_diferentes(self):
        assert _chave_periodo("Mar/2025") < _chave_periodo("Mar/2026")

    def test_ordenacao_lista(self):
        periodos = ["Mar/2026", "Jan/2026", "Dez/2025", "Fev/2026"]
        ordenados = sorted(periodos, key=_chave_periodo)
        assert ordenados == ["Dez/2025", "Jan/2026", "Fev/2026", "Mar/2026"]


# ═══════════════════════════════════════════════════════════════════════
# 3. LÓGICA DE CARDS E VARIAÇÃO (sem Tk, mockando PainelResumo)
# ═══════════════════════════════════════════════════════════════════════

def _make_consolidacao(periodo, cgr=0.0, cgf=0.0, ret=0.0, rp=0.0, rpv=0.0, scg=0.0):
    return {"periodo": periodo, "cgr": cgr, "cgf": cgf,
            "ret": ret, "rp": rp, "rpv": rpv, "scg": scg}


def _make_painel_sem_tk():
    """Cria um PainelResumo sem inicializar a UI real (mocka ctk e banco)."""
    with patch("Src.Views.dashboard_resumo.ctk"), \
         patch("Src.Views.dashboard_resumo.DatabasePMPV") as MockDB:
        MockDB.return_value.__enter__ = MockDB.return_value
        MockDB.return_value.listar_consolidacao_completa.return_value = []
        MockDB.return_value.listar_pmpv_mensal.return_value = []
        MockDB.return_value.fechar = MagicMock()

        from Src.Views.dashboard_resumo import PainelResumo
        painel = object.__new__(PainelResumo)
        painel._consolidacoes = []
        painel._pmpvs = []
        painel._cards = {}

        combo = MagicMock()
        combo.get.return_value = TODOS_OS_ANOS
        painel.combo_ano = combo
        painel.lbl_periodo = MagicMock()

        return painel


class TestFiltrarPorAno:
    def setup_method(self):
        self.painel = _make_painel_sem_tk()
        self.dados = [
            _make_consolidacao("Dez/2025"),
            _make_consolidacao("Jan/2026"),
            _make_consolidacao("Fev/2026"),
        ]

    def test_todos_os_anos_retorna_tudo(self):
        self.painel.combo_ano.get.return_value = TODOS_OS_ANOS
        from Src.Views.dashboard_resumo import PainelResumo
        resultado = PainelResumo._filtrar_por_ano(self.painel, self.dados)
        assert len(resultado) == 3

    def test_filtro_ano_especifico(self):
        self.painel.combo_ano.get.return_value = "2026"
        from Src.Views.dashboard_resumo import PainelResumo
        resultado = PainelResumo._filtrar_por_ano(self.painel, self.dados)
        assert len(resultado) == 2
        assert all("2026" in r["periodo"] for r in resultado)

    def test_filtro_ano_sem_dados(self):
        self.painel.combo_ano.get.return_value = "2024"
        from Src.Views.dashboard_resumo import PainelResumo
        resultado = PainelResumo._filtrar_por_ano(self.painel, self.dados)
        assert resultado == []

    def test_filtro_preserva_ordem(self):
        self.painel.combo_ano.get.return_value = "2026"
        from Src.Views.dashboard_resumo import PainelResumo
        resultado = PainelResumo._filtrar_por_ano(self.painel, self.dados)
        assert resultado[0]["periodo"] == "Jan/2026"
        assert resultado[1]["periodo"] == "Fev/2026"


class TestAtualizarCards:
    def setup_method(self):
        self.painel = _make_painel_sem_tk()
        for chave, _, _ in [
            ("cgr", "", ""), ("ret", "", ""), ("cgf", "", ""),
            ("rp", "", ""), ("rpv", "", ""), ("scg", "", ""),
        ]:
            lbl_valor = MagicMock()
            lbl_variacao = MagicMock()
            self.painel._cards[chave] = (lbl_valor, lbl_variacao)

    def _atualizar(self, consolidacoes):
        from Src.Views.dashboard_resumo import PainelResumo
        PainelResumo._atualizar_cards(self.painel, consolidacoes)

    def test_sem_dados_mostra_traco(self):
        self._atualizar([])
        self.painel.lbl_periodo.configure.assert_called_with(
            text="Nenhum período calculado ainda."
        )
        for chave in self.painel._cards:
            lbl_valor, lbl_variacao = self.painel._cards[chave]
            lbl_valor.configure.assert_called_with(text="—")
            lbl_variacao.configure.assert_called_with(text="")

    def test_um_periodo_sem_variacao(self):
        dados = [_make_consolidacao("Jan/2026", cgr=1_000_000)]
        self._atualizar(dados)
        self.painel.lbl_periodo.configure.assert_called_with(
            text="Período mais recente: Jan/2026"
        )
        lbl_valor, lbl_variacao = self.painel._cards["cgr"]
        lbl_valor.configure.assert_called_with(text="R$ 1.000.000,00")
        lbl_variacao.configure.assert_called_with(text="")

    def test_dois_periodos_variacao_positiva(self):
        dados = [
            _make_consolidacao("Jan/2026", cgr=1_000_000),
            _make_consolidacao("Fev/2026", cgr=1_100_000),
        ]
        self._atualizar(dados)
        lbl_valor, lbl_variacao = self.painel._cards["cgr"]
        lbl_valor.configure.assert_called_with(text="R$ 1.100.000,00")
        call_kwargs = lbl_variacao.configure.call_args[1]
        assert "▲" in call_kwargs["text"]
        assert "+10,0%" in call_kwargs["text"]
        assert "Jan/2026" in call_kwargs["text"]

    def test_dois_periodos_variacao_negativa(self):
        dados = [
            _make_consolidacao("Jan/2026", cgr=1_000_000),
            _make_consolidacao("Fev/2026", cgr=800_000),
        ]
        self._atualizar(dados)
        _, lbl_variacao = self.painel._cards["cgr"]
        call_kwargs = lbl_variacao.configure.call_args[1]
        assert "▼" in call_kwargs["text"]
        assert "-20,0%" in call_kwargs["text"]

    def test_anterior_zero_nao_calcula_variacao(self):
        dados = [
            _make_consolidacao("Jan/2026", cgr=0),
            _make_consolidacao("Fev/2026", cgr=500_000),
        ]
        self._atualizar(dados)
        _, lbl_variacao = self.painel._cards["cgr"]
        lbl_variacao.configure.assert_called_with(text="")

    def test_todos_campos_recebem_valor(self):
        dados = [_make_consolidacao("Jan/2026", cgr=1e6, cgf=2e6, ret=3e6,
                                     rp=4e6, rpv=5e6, scg=6e6)]
        self._atualizar(dados)
        esperados = {
            "cgr": "R$ 1.000.000,00",
            "cgf": "R$ 2.000.000,00",
            "ret": "R$ 3.000.000,00",
            "rp":  "R$ 4.000.000,00",
            "rpv": "R$ 5.000.000,00",
            "scg": "R$ 6.000.000,00",
        }
        for chave, texto_esperado in esperados.items():
            lbl_valor, _ = self.painel._cards[chave]
            lbl_valor.configure.assert_called_with(text=texto_esperado)


# ═══════════════════════════════════════════════════════════════════════
# 4. INTEGRAÇÃO COM BANCO TEMPORÁRIO (SQLite real)
# ═══════════════════════════════════════════════════════════════════════

class TestCarregarDoBanco:
    @pytest.fixture
    def db_temp(self, tmp_path):
        from Src.Database.database import DatabasePMPV
        db = DatabasePMPV(str(tmp_path / "test_dashboard.db"))
        yield db
        db.fechar()

    def test_filtra_periodos_invalidos(self, db_temp):
        db_temp.salvar_pmpv_mensal("TESTE2", 2.0)
        db_temp.salvar_pmpv_mensal("leandro[", 1.5)
        db_temp.salvar_pmpv_mensal("Jan/2026", 2.1)

        pmpvs = db_temp.listar_pmpv_mensal()
        validos = [p for p in pmpvs if _PERIODO_VALIDO.match(p.get("periodo", ""))]
        assert len(validos) == 1
        assert validos[0]["periodo"] == "Jan/2026"

    def test_consolida_multiplos_periodos(self, db_temp):
        for periodo in ["Jan/2026", "Fev/2026", "Mar/2026"]:
            db_temp.criar_periodo_consolidacao(periodo)

        consolidacoes = db_temp.listar_consolidacao_completa()
        validos = [c for c in consolidacoes if _PERIODO_VALIDO.match(c.get("periodo", ""))]
        periodos = [c["periodo"] for c in validos]
        assert "Jan/2026" in periodos
        assert "Fev/2026" in periodos
        assert "Mar/2026" in periodos

    def test_ordenacao_cronologica(self, db_temp):
        for periodo in ["Mar/2026", "Jan/2026", "Dez/2025", "Fev/2026"]:
            db_temp.criar_periodo_consolidacao(periodo)

        consolidacoes = db_temp.listar_consolidacao_completa()
        validos = [c for c in consolidacoes if _PERIODO_VALIDO.match(c.get("periodo", ""))]
        validos.sort(key=lambda c: _chave_periodo(c["periodo"]))
        periodos = [c["periodo"] for c in validos]
        assert periodos == ["Dez/2025", "Jan/2026", "Fev/2026", "Mar/2026"]

    def test_anos_extraidos_para_slicer(self, db_temp):
        for periodo in ["Dez/2025", "Jan/2026", "Fev/2026"]:
            db_temp.criar_periodo_consolidacao(periodo)
        db_temp.salvar_pmpv_mensal("Mar/2024", 1.9)

        consolidacoes = db_temp.listar_consolidacao_completa()
        pmpvs = db_temp.listar_pmpv_mensal()

        validos_cons = [c for c in consolidacoes if _PERIODO_VALIDO.match(c.get("periodo", ""))]
        validos_pmpv = [p for p in pmpvs if _PERIODO_VALIDO.match(p.get("periodo", ""))]

        anos = sorted(
            {_chave_periodo(c["periodo"])[0] for c in validos_cons}
            | {_chave_periodo(p["periodo"])[0] for p in validos_pmpv},
            reverse=True,
        )
        assert anos == [2026, 2025, 2024]

    def test_banco_vazio_retorna_listas_vazias(self, db_temp):
        consolidacoes = db_temp.listar_consolidacao_completa()
        pmpvs = db_temp.listar_pmpv_mensal()
        assert consolidacoes == []
        assert pmpvs == []

    def test_valores_numericos_apos_salvar(self, db_temp):
        db_temp.criar_periodo_consolidacao("Jan/2026")
        db_temp.atualizar_campos_consolidacao("Jan/2026", cgr=86_000_000.0, cgf=79_000_000.0)

        cons = db_temp.buscar_consolidacao("Jan/2026")
        assert float(cons["cgr"]) == pytest.approx(86_000_000.0)
        assert float(cons["cgf"]) == pytest.approx(79_000_000.0)

    def test_pmpv_salvo_e_recuperado(self, db_temp):
        db_temp.salvar_pmpv_mensal("Fev/2026", 1.9988)
        valor = db_temp.buscar_pmpv_mensal("Fev/2026")
        assert valor == pytest.approx(1.9988, rel=1e-4)
