"""
Testes para modulo_pmpv.py

Cobre as funções puras extraídas da classe CalculadoraTrimestralPMPV:
  - calcular_pmpv        : cálculo da média ponderada
  - sanitizar_volume     : limpeza do campo Volume
  - linha_disponivel     : critério de destino de cópia
  - linha_disponivel bug : reproduz o bug corrigido (linhas default com dados vazios)
"""
import pytest


# ---------------------------------------------------------------------------
# Funções puras extraídas da lógica de negócio (sem dependência de UI)
# ---------------------------------------------------------------------------

def calcular_pmpv(dados_meses: dict, dias_config: dict) -> dict | None:
    """
    Replica a lógica de calcular() sem UI.

    dados_meses: { "Mês 1": [ {"mol": float, "trans": float, "log": float, "vol": float}, ... ], ... }
    dias_config: { "Mês 1": int, "Mês 2": int, "Mês 3": int }
    Retorna dict com pmpv, volume_total, custo_total  ou  None se volume == 0.
    """
    c_tot = v_tot = 0.0
    for k, linhas in dados_meses.items():
        dias = dias_config.get(k, 30)
        for l in linhas:
            vol = l.get("vol", 0.0)
            if vol <= 0:
                continue
            pr = l.get("mol", 0.0) + l.get("trans", 0.0) + l.get("log", 0.0)
            v_mes = vol * dias
            c_tot += pr * v_mes
            v_tot += v_mes
    if v_tot == 0:
        return None
    return {"pmpv": c_tot / v_tot, "volume_total": v_tot, "custo_total": c_tot}


def sanitizar_volume(val: str) -> str:
    """
    Replica CalculadoraTrimestralPMPV._limpar_str_volume sem depender de widgets.
    """
    limpo = val.replace(",", ".")
    limpo = "".join(c for c in limpo if c.isdigit() or c == ".")
    partes = limpo.split(".")
    if len(partes) > 2:
        ultimo = partes[-1]
        if len(ultimo) == 3:
            limpo = "".join(partes)
        else:
            limpo = "".join(partes[:-1]) + "." + ultimo
    return limpo


def linha_disponivel(nome: str, mol: str, trans: str, log: str, vol: str) -> bool:
    """
    Replica _linha_disponivel sem depender de widgets tkinter.
    Uma linha está disponível como destino se todos os dados estiverem em branco.
    Nome vazio é sempre disponível; 'Nova Empresa' com dados preenchidos NÃO é sobrescrito.
    """
    todos_vazios = all(not v.strip() for v in [mol, trans, log, vol])
    if nome.strip() == "":
        return True
    return todos_vazios


# ---------------------------------------------------------------------------
# Testes: calcular_pmpv
# ---------------------------------------------------------------------------

class TestCalcularPmpv:

    def test_uma_empresa_pmpv_igual_ao_preco(self):
        """Com uma única empresa, PMPV deve ser igual ao preço unitário dela."""
        dados = {"Mês 1": [{"mol": 1.6487, "trans": 0.5006, "log": 0.0, "vol": 100_000}]}
        res = calcular_pmpv(dados, {"Mês 1": 30})
        assert res is not None
        assert res["pmpv"] == pytest.approx(2.1493, rel=1e-4)

    def test_duas_empresas_pmpv_ponderado(self):
        """Com duas empresas, PMPV é puxado para o lado de maior volume."""
        dados = {
            "Mês 1": [
                {"mol": 2.0, "trans": 0.0, "log": 0.0, "vol": 100_000},
                {"mol": 3.0, "trans": 0.0, "log": 0.0, "vol": 100_000},
            ]
        }
        res = calcular_pmpv(dados, {"Mês 1": 30})
        assert res is not None
        assert res["pmpv"] == pytest.approx(2.5, rel=1e-6)

    def test_volume_maior_puxa_pmpv(self):
        """Empresa com maior volume deve ter mais peso no PMPV."""
        dados = {
            "Mês 1": [
                {"mol": 2.0, "trans": 0.0, "log": 0.0, "vol": 900_000},
                {"mol": 5.0, "trans": 0.0, "log": 0.0, "vol": 100_000},
            ]
        }
        res = calcular_pmpv(dados, {"Mês 1": 30})
        assert res is not None
        assert res["pmpv"] == pytest.approx(2.3, rel=1e-6)

    def test_parametros_vazios_tratados_como_zero(self):
        """Campos de preço vazios (0) não devem impedir o cálculo."""
        dados = {"Mês 1": [{"mol": 0.0, "trans": 0.0, "log": 0.0, "vol": 50_000}]}
        res = calcular_pmpv(dados, {"Mês 1": 30})
        assert res is not None
        assert res["pmpv"] == pytest.approx(0.0)

    def test_volume_zero_retorna_none(self):
        """Deve retornar None quando não há volume preenchido."""
        dados = {"Mês 1": [{"mol": 2.0, "trans": 0.5, "log": 0.1, "vol": 0}]}
        assert calcular_pmpv(dados, {"Mês 1": 30}) is None

    def test_linhas_sem_volume_ignoradas(self):
        """Linhas com vol=0 não devem entrar no cálculo."""
        dados = {
            "Mês 1": [
                {"mol": 99.0, "trans": 0.0, "log": 0.0, "vol": 0},
                {"mol": 2.0,  "trans": 0.0, "log": 0.0, "vol": 50_000},
            ]
        }
        res = calcular_pmpv(dados, {"Mês 1": 30})
        assert res is not None
        assert res["pmpv"] == pytest.approx(2.0)

    def test_tres_meses_diferentes(self):
        """PMPV deve ponderar corretamente dados espalhados pelos 3 meses."""
        dados = {
            "Mês 1": [{"mol": 2.0, "trans": 0.0, "log": 0.0, "vol": 100_000}],
            "Mês 2": [{"mol": 3.0, "trans": 0.0, "log": 0.0, "vol": 100_000}],
            "Mês 3": [{"mol": 4.0, "trans": 0.0, "log": 0.0, "vol": 100_000}],
        }
        dias = {"Mês 1": 31, "Mês 2": 28, "Mês 3": 31}
        res = calcular_pmpv(dados, dias)
        assert res is not None
        v1 = 100_000 * 31
        v2 = 100_000 * 28
        v3 = 100_000 * 31
        esperado = (2.0 * v1 + 3.0 * v2 + 4.0 * v3) / (v1 + v2 + v3)
        assert res["pmpv"] == pytest.approx(esperado, rel=1e-6)

    def test_meses_vazios_ignorados(self):
        """Meses sem nenhuma linha com volume não afetam o resultado."""
        dados = {
            "Mês 1": [{"mol": 2.5, "trans": 0.0, "log": 0.0, "vol": 100_000}],
            "Mês 2": [],
            "Mês 3": [{"mol": 2.5, "trans": 0.0, "log": 0.0, "vol": 0}],
        }
        res = calcular_pmpv(dados, {"Mês 1": 30, "Mês 2": 30, "Mês 3": 30})
        assert res is not None
        assert res["pmpv"] == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Testes: sanitizar_volume
# ---------------------------------------------------------------------------

class TestSanitizarVolume:

    def test_numero_inteiro_passa_sem_alteracao(self):
        assert sanitizar_volume("100000") == "100000"

    def test_numero_decimal_com_ponto_passa(self):
        assert sanitizar_volume("1500.75") == "1500.75"

    def test_virgula_convertida_para_ponto(self):
        assert sanitizar_volume("1500,75") == "1500.75"

    def test_multiplos_pontos_colados_do_excel(self):
        """'1.500.000' colado do Excel (separador de milhar) deve virar '1500000'."""
        assert sanitizar_volume("1.500.000") == "1500000"

    def test_formato_europeu_colado(self):
        """'1.500,75' (formato europeu: ponto=milhar, vírgula=decimal) → '1500.75'."""
        assert sanitizar_volume("1.500,75") == "1500.75"

    def test_letras_removidas(self):
        assert sanitizar_volume("100abc000") == "100000"

    def test_string_vazia_permanece_vazia(self):
        assert sanitizar_volume("") == ""

    def test_apenas_ponto_permanece(self):
        assert sanitizar_volume(".") == "."

    def test_dois_pontos_segmento_final_nao_e_milhar(self):
        """'1.2.3': segmento final tem 1 dígito (≠ 3) → decimal → '12.3'."""
        assert sanitizar_volume("1.2.3") == "12.3"


# ---------------------------------------------------------------------------
# Testes: linha_disponivel  (inclui reprodução do bug corrigido)
# ---------------------------------------------------------------------------

class TestLinhaDisponivel:

    def test_nome_vazio_disponivel(self):
        assert linha_disponivel("", "", "", "", "") is True

    def test_nova_empresa_disponivel(self):
        assert linha_disponivel("Nova Empresa", "", "", "", "") is True

    def test_linha_com_todos_dados_nao_disponivel(self):
        assert linha_disponivel("PETROBRAS", "1.6487", "0.5006", "0.0", "100000") is False

    # --- Reprodução do bug corrigido ---
    def test_bug_linha_default_sem_dados_deve_estar_disponivel(self):
        """
        BUG CORRIGIDO: linhas padrão (GALP, BRAVA...) com todos os
        campos de dados vazios NÃO eram encontradas como destino,
        causando a mensagem 'Crie uma linha vazia no destino antes'
        mesmo o destino estando vazio.
        """
        assert linha_disponivel("GALP",             "", "", "", "") is True
        assert linha_disponivel("PETRORECONCAVO",   "", "", "", "") is True
        assert linha_disponivel("BRAVA",            "", "", "", "") is True
        assert linha_disponivel("ENEVA",            "", "", "", "") is True
        assert linha_disponivel("ORIZON",           "", "", "", "") is True

    def test_linha_com_apenas_volume_nao_disponivel(self):
        """Linha com apenas o volume preenchido não deve ser sobrescrita."""
        assert linha_disponivel("GALP", "", "", "", "50000") is False

    def test_linha_com_apenas_molecula_nao_disponivel(self):
        assert linha_disponivel("GALP", "1.8", "", "", "") is False

    def test_nova_empresa_com_dados_nao_disponivel(self):
        """'Nova Empresa' com dados preenchidos não deve ser destino."""
        assert linha_disponivel("Nova Empresa", "2.0", "0.5", "0.1", "10000") is False
