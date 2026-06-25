from __future__ import annotations

from pathlib import Path

import pytest

from Src.Services.servicos_auditoria import (
    RegrasAuditoria,
    XMLItem,
    PIS_RATE,
    COFINS_RATE,
    PIS_COFINS_RATE,
    CST_ICMS_ZERO,
)


# ════════════════════════════════════════════════════════════════════════════
# Constantes regulatórias
# ════════════════════════════════════════════════════════════════════════════

class TestConstantes:
    def test_pis_cofins_soma_correta(self):
        assert PIS_COFINS_RATE == pytest.approx(PIS_RATE + COFINS_RATE)
        assert PIS_COFINS_RATE == pytest.approx(0.0925)

    def test_csts_icms_zero(self):
        assert "40" in CST_ICMS_ZERO
        assert "41" in CST_ICMS_ZERO
        assert "50" in CST_ICMS_ZERO
        assert "60" in CST_ICMS_ZERO
        assert "00" not in CST_ICMS_ZERO


# ════════════════════════════════════════════════════════════════════════════
# Cálculos CGR
# ════════════════════════════════════════════════════════════════════════════

class TestCalcularCGRLiquido:
    def test_caso_dez_2025_da_doc(self):
        # Valor do docstring: (112.441.134,15 − 12.440.114,91) × 0,9075 ≈ 90.750.924,96
        cgr = RegrasAuditoria.calcular_cgr_liquido(112_441_134.15, 12_440_114.91)
        assert cgr == pytest.approx(90_750_924.96, rel=1e-6)

    def test_caso_nov_2025(self):
        cgr = RegrasAuditoria.calcular_cgr_liquido(117_947_652.94, 14_463_268.28)
        assert cgr == pytest.approx(93_912_079.08, rel=1e-6)

    def test_icms_zero(self):
        # Sem ICMS, CGR = valor × (1 − PIS_COFINS)
        cgr = RegrasAuditoria.calcular_cgr_liquido(1000.0, 0.0)
        assert cgr == pytest.approx(1000.0 * (1 - 0.0925))

    def test_valor_zero(self):
        assert RegrasAuditoria.calcular_cgr_liquido(0.0, 0.0) == 0.0


class TestCalcularSTributos:
    def test_icms_12_pct(self):
        # 1000 × (1 - 0.12) × (1 - 0.0925) = 1000 × 0.88 × 0.9075
        esperado = 1000 * 0.88 * 0.9075
        assert RegrasAuditoria.calcular_s_tributos(1000.0, 0.12) == pytest.approx(esperado)

    def test_icms_zero(self):
        assert RegrasAuditoria.calcular_s_tributos(1000.0, 0.0) == pytest.approx(1000 * 0.9075)

    def test_icms_100_pct_resulta_zero(self):
        assert RegrasAuditoria.calcular_s_tributos(1000.0, 1.0) == 0.0


# ════════════════════════════════════════════════════════════════════════════
# Detecção de tipo
# ════════════════════════════════════════════════════════════════════════════

class TestDetectarTipoXML:
    def test_nfe(self, tmp_path):
        f = tmp_path / "nf.xml"
        f.write_text("<?xml version='1.0'?><nfeProc><NFe></NFe></nfeProc>", encoding="utf-8")
        assert RegrasAuditoria.detectar_tipo_xml(f) == "nfe"

    def test_cte(self, tmp_path):
        f = tmp_path / "ct.xml"
        f.write_text("<?xml version='1.0'?><cteProc><CTe></CTe></cteProc>", encoding="utf-8")
        assert RegrasAuditoria.detectar_tipo_xml(f) == "cte"

    def test_desconhecido(self, tmp_path):
        f = tmp_path / "x.xml"
        f.write_text("<?xml version='1.0'?><Outro/>", encoding="utf-8")
        assert RegrasAuditoria.detectar_tipo_xml(f) == "desconhecido"

    def test_arquivo_inexistente(self, tmp_path):
        # Não levanta — captura exceção e retorna 'desconhecido'
        assert RegrasAuditoria.detectar_tipo_xml(tmp_path / "no.xml") == "desconhecido"


# ════════════════════════════════════════════════════════════════════════════
# Parse NF-e
# ════════════════════════════════════════════════════════════════════════════

NFE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe>
      <ide><nNF>123456</nNF></ide>
      <det>
        <prod>
          <uCom>M3</uCom>
          <qCom>500.00</qCom>
        </prod>
        <imposto>
          <ICMS><ICMS00><pICMS>12.00</pICMS></ICMS00></ICMS>
        </imposto>
      </det>
      <total>
        <ICMSTot>
          <vNF>10000.00</vNF>
          <vICMS>1200.00</vICMS>
          <vPIS>165.00</vPIS>
          <vCOFINS>760.00</vCOFINS>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>
"""


class TestParseNFe:
    @pytest.fixture
    def xml_path(self, tmp_path):
        p = tmp_path / "nfe.xml"
        p.write_text(NFE_XML, encoding="utf-8")
        return p

    def test_extrai_numero(self, xml_path):
        d = RegrasAuditoria.parse_nfe(xml_path)
        assert d["numero"] == "123456"
        assert d["tipo"] == "NF-e"

    def test_valor_total(self, xml_path):
        assert RegrasAuditoria.parse_nfe(xml_path)["valor_total"] == 10000.0

    def test_icms_em_reais(self, xml_path):
        assert RegrasAuditoria.parse_nfe(xml_path)["icms"] == 1200.0

    def test_icms_taxa_via_picms(self, xml_path):
        # pICMS = 12.00 → 0.12
        assert RegrasAuditoria.parse_nfe(xml_path)["icms_taxa"] == pytest.approx(0.12)

    def test_pis_cofins(self, xml_path):
        d = RegrasAuditoria.parse_nfe(xml_path)
        assert d["pis"] == 165.0
        assert d["cofins"] == 760.0

    def test_volume_m3(self, xml_path):
        d = RegrasAuditoria.parse_nfe(xml_path)
        assert d["volume_total"] == 500.0
        assert d["volume"] == 500

    def test_xml_invalido_retorna_erro(self, tmp_path):
        f = tmp_path / "bad.xml"
        f.write_text("não é xml", encoding="utf-8")
        d = RegrasAuditoria.parse_nfe(f)
        assert "erro" in d

    def test_taxa_derivada_quando_picms_ausente(self, tmp_path):
        xml = """<?xml version="1.0"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe>
    <ide><nNF>1</nNF></ide>
    <total><ICMSTot>
      <vNF>1000.00</vNF><vICMS>200.00</vICMS>
      <vPIS>0</vPIS><vCOFINS>0</vCOFINS>
    </ICMSTot></total>
  </infNFe></NFe>
</nfeProc>"""
        f = tmp_path / "x.xml"
        f.write_text(xml, encoding="utf-8")
        d = RegrasAuditoria.parse_nfe(f)
        # Sem pICMS → deriva via vICMS/vNF = 0.2
        assert d["icms_taxa"] == pytest.approx(0.2)


# ════════════════════════════════════════════════════════════════════════════
# Parse CT-e
# ════════════════════════════════════════════════════════════════════════════

CTE_XML_NORMAL = """<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="http://www.portalfiscal.inf.br/cte">
  <CTe>
    <infCte>
      <ide><nCT>789</nCT></ide>
      <vPrest><vTPrest>5000.00</vTPrest></vPrest>
      <imp>
        <ICMS><ICMS00><CST>00</CST><pICMS>7.00</pICMS><vICMS>350.00</vICMS></ICMS00></ICMS>
        <vPIS>82.50</vPIS>
        <vCOFINS>380.00</vCOFINS>
      </imp>
      <infCTeNorm>
        <infCarga>
          <infQ><cUnid>00</cUnid><qCarga>200.00</qCarga></infQ>
        </infCarga>
      </infCTeNorm>
    </infCte>
  </CTe>
</cteProc>
"""

CTE_XML_ISENTO = """<?xml version="1.0" encoding="UTF-8"?>
<cteProc xmlns="http://www.portalfiscal.inf.br/cte">
  <CTe><infCte>
    <ide><nCT>999</nCT></ide>
    <vPrest><vTPrest>1000.00</vTPrest></vPrest>
    <imp>
      <ICMS><ICMS40><CST>40</CST></ICMS40></ICMS>
    </imp>
  </infCte></CTe>
</cteProc>
"""


class TestParseCTe:
    def test_normal(self, tmp_path):
        f = tmp_path / "cte.xml"
        f.write_text(CTE_XML_NORMAL, encoding="utf-8")
        d = RegrasAuditoria.parse_cte(f)
        assert d["tipo"] == "CT-e"
        assert d["numero"] == "789"
        assert d["valor_total"] == 5000.0
        assert d["icms"] == 350.0
        assert d["icms_taxa"] == pytest.approx(0.07)
        assert d["pis"] == 82.5
        assert d["cofins"] == 380.0
        assert d["volume_total"] == 200.0
        assert d["unidade_volume"] == "M3"

    def test_cte_isento_zera_icms(self, tmp_path):
        f = tmp_path / "iso.xml"
        f.write_text(CTE_XML_ISENTO, encoding="utf-8")
        d = RegrasAuditoria.parse_cte(f)
        assert d["icms"] == 0.0
        assert d["icms_taxa"] == 0.0

    def test_xml_invalido(self, tmp_path):
        f = tmp_path / "bad.xml"
        f.write_text("lixo", encoding="utf-8")
        assert "erro" in RegrasAuditoria.parse_cte(f)


# ════════════════════════════════════════════════════════════════════════════
# XMLItem dataclass
# ════════════════════════════════════════════════════════════════════════════

class TestXMLItem:
    def test_criacao(self):
        item = XMLItem(
            empresa="ACME", tipo="NF-e", numero="1",
            valor_total=1000.0, icms=120.0, icms_taxa=0.12,
            pis=16.5, cofins=76.0, volume=100, status="OK", volume_total=100.0,
        )
        assert item.empresa == "ACME"
        assert item.tipo == "NF-e"
        assert item.valor_total == 1000.0
