from __future__ import annotations

import pytest

from Src.Services.ret.servicos_ret import RegrasRET, PIS_COFINS_RATE, TAXA_EUR_BRL, _extrair_mes_caminho


class TestConstantes:
    def test_taxas(self):
        assert PIS_COFINS_RATE == 0.0925
        assert TAXA_EUR_BRL == 6.0


# ════════════════════════════════════════════════════════════════════════════
# identificar_tipo
# ════════════════════════════════════════════════════════════════════════════

class TestIdentificarTipo:
    def test_eat(self):
        assert RegrasRET.identificar_tipo(r"C:\dados\EAT_2026\arq.pdf") == "EAT"

    def test_ec_exato(self):
        assert RegrasRET.identificar_tipo(r"C:\dados\EC\arq.pdf") == "EC"

    def test_ec_prefixo(self):
        assert RegrasRET.identificar_tipo(r"C:\dados\EC 2026\x.pdf") == "EC"

    def test_penalidade_despesa(self):
        assert RegrasRET.identificar_tipo(r"C:\PENALIDADES DESPESA\x.pdf") == "Penalidades (Despesa)"

    def test_penalidade_receita(self):
        assert RegrasRET.identificar_tipo(r"C:\PENALIDADES RECEITA\x.pdf") == "Penalidades (Receita)"

    def test_penalidade_generica(self):
        assert RegrasRET.identificar_tipo(r"C:\PENALIDADES\x.pdf") == "Penalidades"

    def test_top(self):
        assert RegrasRET.identificar_tipo(r"C:\TOP\x.pdf") == "TOP"

    def test_outros(self):
        assert RegrasRET.identificar_tipo(r"C:\qualquer\x.pdf") == "Outros"


# ════════════════════════════════════════════════════════════════════════════
# extrair_empresa
# ════════════════════════════════════════════════════════════════════════════

class TestExtrairEmpresa:
    def test_no_nome_arquivo(self):
        assert RegrasRET.extrair_empresa(r"C:\d\PETROBRAS_ND_001.pdf") == "PETROBRAS"

    def test_na_pasta_pai(self):
        assert RegrasRET.extrair_empresa(r"C:\GALP\arq.pdf") == "GALP"

    def test_nao_encontrada(self):
        assert RegrasRET.extrair_empresa(r"C:\xyz\arq.pdf") == "N/A"


# ════════════════════════════════════════════════════════════════════════════
# extrair_tipo_nota
# ════════════════════════════════════════════════════════════════════════════

class TestExtrairTipoNota:
    @pytest.mark.parametrize("nome,esperado", [
        ("ND_DEBITO.pdf", "Débito"),
        ("nota_credito.pdf", "Crédito"),
        ("NDPFP_001.pdf", "Débito"),
        ("ND123.pdf", "Débito"),
        ("NC_456.pdf", "Crédito"),
        # NF/NFE/DANFE precisam de word-boundary real (separados por espaço/início/fim)
        ("DANFE 123.pdf", "NF"),
        ("NFE 789.pdf", "NF"),
        ("CT-E.pdf", "NF"),
        ("aleatorio.pdf", "N/A"),
    ])
    def test_padroes(self, nome, esperado):
        assert RegrasRET.extrair_tipo_nota(f"C:\\d\\{nome}") == esperado


# ════════════════════════════════════════════════════════════════════════════
# _extrair_mes_caminho
# ════════════════════════════════════════════════════════════════════════════

class TestExtrairMesCaminho:
    def test_mes_e_ano_na_pasta(self):
        mes, ano = _extrair_mes_caminho(r"C:\dados\JANEIRO_2026\x.pdf")
        assert mes == 1
        assert ano == 2026

    def test_mes_abrev(self):
        mes, _ = _extrair_mes_caminho(r"C:\d\JAN 2026\arq.pdf")
        assert mes == 1

    def test_subpasta_mais_proxima_tem_prioridade(self):
        # Tem JAN na pasta superior e FEV na subpasta — FEV deve ganhar
        mes, _ = _extrair_mes_caminho(r"C:\JANEIRO_2025\FEVEREIRO\x.pdf")
        assert mes == 2

    def test_sem_mes(self):
        from datetime import date
        mes, ano = _extrair_mes_caminho(r"C:\xyz\arq.pdf")
        assert mes == 0
        assert ano == date.today().year


# ════════════════════════════════════════════════════════════════════════════
# extrair_calc_exato
# ════════════════════════════════════════════════════════════════════════════

class TestExtrairCalcExato:
    def test_padrao_volume_x_taxa(self):
        texto = "Cálculo: 1000,50 x R$ 10,00"
        assert RegrasRET.extrair_calc_exato(texto) == pytest.approx(10005.0)

    def test_sem_padrao(self):
        assert RegrasRET.extrair_calc_exato("texto qualquer sem formula") == 0.0

    def test_zero_em_um_lado(self):
        assert RegrasRET.extrair_calc_exato("0 x R$ 100,00") == 0.0


# ════════════════════════════════════════════════════════════════════════════
# calcular_ret
# ════════════════════════════════════════════════════════════════════════════

class TestCalcularRET:
    def test_so_eat(self):
        dados = [
            {"tipo_encargo": "EAT", "valor_total": 1000.0},
            {"tipo_encargo": "EAT", "valor_total": 500.0},
        ]
        r = RegrasRET.calcular_ret(dados)
        assert r["eat_bruto"] == 1500.0
        assert r["ec_docs_total"] == 0.0
        # EC = 1500 × (1 − 0.0925) + 0 = 1361.25
        assert r["ec"] == pytest.approx(1500 * (1 - 0.0925))
        assert r["ret"] == r["ec"]

    def test_eat_e_ec(self):
        dados = [
            {"tipo_encargo": "EAT", "valor_total": 1000.0},
            {"tipo_encargo": "EC", "valor_total": 200.0},
        ]
        r = RegrasRET.calcular_ret(dados)
        assert r["eat_bruto"] == 1000.0
        assert r["ec_docs_total"] == 200.0
        # EC = 1000 × 0.9075 + 200
        assert r["ec"] == pytest.approx(1000 * 0.9075 + 200)

    def test_outros_separados(self):
        dados = [
            {"tipo_encargo": "TOP", "valor_total": 500.0},
            {"tipo_encargo": "Penalidades", "valor_total": 100.0},
        ]
        r = RegrasRET.calcular_ret(dados)
        assert r["eat_bruto"] == 0.0
        assert r["ec_docs_total"] == 0.0
        assert r["ec"] == 0.0
        assert len(r["outros_docs"]) == 2

    def test_lista_vazia(self):
        r = RegrasRET.calcular_ret([])
        assert r["eat_bruto"] == 0.0
        assert r["ret"] == 0.0
        assert r["pis_cofins_rate"] == 0.0925


# ════════════════════════════════════════════════════════════════════════════
# PDFs com o número quebrado por espaço ("1 .335,86") — conferidos com a planilha Jan–Set/26
# ════════════════════════════════════════════════════════════════════════════

TEXTO_GALP_ND82 = """GALP ENERGIA BRASIL S.A
NOTA DE DÉBITO 82/2026
DATA: 08/04/2026
Descrição:
VALOR
(R$)
Encargo de Capacidade Não Utilizada 1.402,60
Encargo de Custo Fixo 677,69
VALOR TOTAL DO DOCUMENTO 2 .080,29
Dados Bancário:
Banco: 341 – Banco Itaú 15/04/2026
"""

TEXTO_GALP_ND007 = """GALP ENERGIA BRASIL S.A
NOTA DE DÉBITO Nº 007/2026
Penalidade de Variação 0,00
Encargo de Capacidade Não Utilizada 657,97
Encargo de Custo Fixo 677,89
VALOR TOTAL DO DOCUMENTO 1 .335,86
"""

TEXTO_PETRORECONCAVO = """Nº 90009873
NOTA DE DÉBITO
Valor Total da Fatura #REF!
Unidade de Medida: m³
Quantidade: 6 .139.849,00
Preço unitário sem tributos (R$) 0,0058
Valor Líquido (sem tributos) (R$): 35.474,95
PIS e COFINS (R$): 3.615,90
Preço unitário com tributos (R$): 0,0064
Valor Total (com tributos) (R$): 39.090,86
"""


@pytest.mark.parametrize("texto, esperado", [
    (TEXTO_GALP_ND82, 2080.29),         # lia só o pedaço depois do espaço (1.402,60)
    (TEXTO_GALP_ND007, 1335.86),        # lia 677,89
    (TEXTO_PETRORECONCAVO, 39090.86),   # lia a quantidade (139.849,00) como valor
])
def test_valor_total_de_pdf_com_numero_quebrado_por_espaco(monkeypatch, texto, esperado):
    monkeypatch.setattr("Src.Services.ret.servicos_ret.read_pdf_text", lambda *a, **k: (texto, "TEXTO"))
    dados = RegrasRET.extrair_dados_pdf(r"C:\RET\EAT fev26\EAT\ND 000 - COPERGAS.pdf")
    assert dados["valor_total"] == pytest.approx(esperado)
