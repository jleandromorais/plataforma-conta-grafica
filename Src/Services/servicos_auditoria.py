import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple, List
import pdfplumber
from dataclasses import dataclass

from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED, read_pdf_text, pytesseract

# ── Fórmula regulatória CGR ──────────────────────────────────────────────────
# Validada contra a planilha "Conta Gráfica e Apuração de Custos" (Jun25→Dez25+):
#
#   Por documento individual:
#     ICMS_R$   = valor_total × ICMS_taxa
#     s/tributos = valor_total × (1 − ICMS_taxa) × (1 − PIS_RATE − COFINS_RATE)
#
#   CGR total:
#     CGR = Σ s/tributos_i  =  (Σ valor_i − Σ ICMS_R$_i) × (1 − PIS_RATE − COFINS_RATE)
#
#   Verificação:
#     Dez/25: (112.441.134,15 − 12.440.114,91) × 0,9075 = 90.750.924,96 ✓
#     Nov/25: (117.947.652,94 − 14.463.268,28) × 0,9075 = 93.912.079,08 ✓
#     Out/25: (121.625.390,74 − 14.842.587,78) × 0,9075 = 96.905.393,69 ✓
#
#   ATENÇÃO: ICMS_R$ é sempre calculado como valor × ICMS_taxa (%).
#   Não usar o vICMS do XML diretamente na fórmula — usá-lo apenas para
#   derivar a taxa: icms_taxa = vICMS / vNF  (ou pICMS/100 quando disponível).
PIS_RATE    = 0.0165
COFINS_RATE = 0.076
PIS_COFINS_RATE = PIS_RATE + COFINS_RATE   # 0.0925

# CSTs de ICMS que representam isenção/não-incidência (ICMS = 0%)
CST_ICMS_ZERO = {'40', '41', '50', '51', '60', '90'}


@dataclass
class XMLItem:
    """Representa um item auditado de XML fiscal."""
    empresa: str
    tipo: str
    numero: str
    valor_total: float
    icms: float          # R$ (vICMS do XML)
    icms_taxa: float     # % (ex: 0.12, 0.205, 0.07)
    pis: float
    cofins: float
    volume: int
    status: str
    volume_total: float


class RegrasAuditoria:

    # ── CGR ──────────────────────────────────────────────────────────────────

    @staticmethod
    def calcular_cgr_liquido(valor_total: float, icms_total: float) -> float:
        """CGR líquido a partir de totais agregados.

        Args:
            valor_total: Σ Compra c/tributos de todos os documentos.
            icms_total:  Σ ICMS_R$ (calculado como valor_i × icms_taxa_i).
        """
        return (valor_total - icms_total) * (1.0 - PIS_COFINS_RATE)

    @staticmethod
    def calcular_s_tributos(valor: float, icms_taxa: float) -> float:
        """Compra s/tributos de um único documento.

        Args:
            valor:      Compra c/tributos (vNF / vTPrest).
            icms_taxa:  ICMS em decimal (ex: 0.12 para 12%).
        """
        return valor * (1.0 - icms_taxa) * (1.0 - PIS_COFINS_RATE)

    # ── Detecção de tipo ─────────────────────────────────────────────────────

    @staticmethod
    def detectar_tipo_xml(xml_path: Path) -> str:
        """Detecta se é NF-e ou CT-e pelo conteúdo."""
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                cabecalho = f.read(500)
            if 'nfeProc' in cabecalho or 'NFe' in cabecalho:
                return 'nfe'
            if 'cteProc' in cabecalho or 'CTe' in cabecalho:
                return 'cte'
        except Exception:
            pass
        return 'desconhecido'

    # ── NF-e ─────────────────────────────────────────────────────────────────

    @staticmethod
    def parse_nfe(xml_path: Path) -> Dict:
        """Extrai dados de uma NF-e.

        Campos retornados
        -----------------
        tipo, numero, valor_total, icms (R$), icms_taxa (decimal),
        pis (R$), cofins (R$), volume_total (m³), volume (int).

        Fórmula ICMS_taxa
        -----------------
        1ª opção: pICMS do primeiro <det> (mais preciso, ex: 20.5 → 0.205).
        2ª opção: vICMS / vNF (derivado, pode ter arredondamento mínimo).
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

            # ── valores totais ────────────────────────────────────────────────
            numero    = root.find('.//nfe:ide/nfe:nNF', ns)
            valor_ext = root.find('.//nfe:total/nfe:vNFTot', ns)
            valor_tag = root.find('.//nfe:total/nfe:ICMSTot/nfe:vNF', ns)
            icms_tag  = root.find('.//nfe:total/nfe:ICMSTot/nfe:vICMS', ns)
            pis_tag   = root.find('.//nfe:total/nfe:ICMSTot/nfe:vPIS', ns)
            cofins_tag = root.find('.//nfe:total/nfe:ICMSTot/nfe:vCOFINS', ns)

            valor = (float(valor_ext.text) if valor_ext is not None
                     else float(valor_tag.text) if valor_tag is not None
                     else 0.0)
            icms_r  = float(icms_tag.text)   if icms_tag   is not None else 0.0
            pis_r   = float(pis_tag.text)    if pis_tag    is not None else 0.0
            cofins_r = float(cofins_tag.text) if cofins_tag is not None else 0.0

            # ── ICMS taxa (%) ─────────────────────────────────────────────────
            # 1ª opção: pICMS do primeiro item do documento
            icms_taxa = 0.0
            for det in root.findall('.//nfe:det', ns):
                p = det.find('.//nfe:pICMS', ns)
                if p is not None and p.text:
                    try:
                        icms_taxa = float(p.text) / 100.0
                        break
                    except ValueError:
                        pass

            # 2ª opção: derivar do total (fallback seguro)
            if icms_taxa == 0.0 and valor > 0:
                icms_taxa = icms_r / valor

            # ── volume M3 ─────────────────────────────────────────────────────
            UNIDADES_M3 = {'M3', 'M³', 'M 3', 'M3.'}
            vol_m3 = 0.0

            for det in root.findall('.//nfe:det', ns):
                u_com = det.find('nfe:prod/nfe:uCom', ns)
                q_com = det.find('nfe:prod/nfe:qCom', ns)
                if u_com is not None and q_com is not None:
                    if u_com.text.strip().upper() in UNIDADES_M3:
                        try:
                            vol_m3 += float(q_com.text)
                        except ValueError:
                            pass

            # Fallback 1: qVol
            if vol_m3 == 0.0:
                for vol in root.findall('.//nfe:vol', ns):
                    q = vol.find('nfe:qVol', ns)
                    if q is not None and q.text:
                        try:
                            vol_m3 += float(q.text)
                        except ValueError:
                            pass

            # Fallback 2: pesoL
            if vol_m3 == 0.0:
                peso = root.find('.//nfe:vol/nfe:pesoL', ns)
                if peso is not None and peso.text:
                    try:
                        vol_m3 = float(peso.text)
                    except ValueError:
                        pass

            return {
                'tipo':         'NF-e',
                'numero':       numero.text if numero is not None else 'N/A',
                'valor_total':  valor,
                'icms':         icms_r,
                'icms_taxa':    icms_taxa,
                'pis':          pis_r,
                'cofins':       cofins_r,
                'volume_total': vol_m3,
                'volume':       int(vol_m3),
            }
        except Exception as e:
            return {'erro': str(e)}

    # ── CT-e ─────────────────────────────────────────────────────────────────

    @staticmethod
    def parse_cte(xml_path: Path) -> Dict:
        """Extrai dados de um CT-e.

        Campos retornados
        -----------------
        tipo, numero, valor_total, icms (R$), icms_taxa (decimal),
        pis (R$), cofins (R$), volume_total (m³), volume (int).

        Regras de ICMS_taxa
        -------------------
        • CST 40/41/50/51/60/90 → isenção/não incidência → icms_taxa = 0
        • Demais CSTs (00, 20…): usar pICMS/100 do bloco ICMS.
          Fallback: vICMS / vTPrest.

        Regras de volume
        ----------------
        • cUnid == '00' (M³): usar qCarga.
        • Outros (mmbtu, kg …): o CT-e é de transporte puro → volume = 0
          (caso TAG, Mastergas remessa interna, etc.).
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            ns = {'cte': 'http://www.portalfiscal.inf.br/cte'}

            numero      = root.find('.//cte:ide/cte:nCT', ns)
            valor_total = root.find('.//cte:vPrest/cte:vTPrest', ns)
            pis_tag     = root.find('.//cte:vPIS', ns)
            cofins_tag  = root.find('.//cte:vCOFINS', ns)

            valor   = float(valor_total.text) if valor_total is not None else 0.0
            pis_r   = float(pis_tag.text)    if pis_tag    is not None else 0.0
            cofins_r = float(cofins_tag.text) if cofins_tag is not None else 0.0

            # ── ICMS ─────────────────────────────────────────────────────────
            cst_node    = root.find('.//cte:ICMS//cte:CST', ns)
            p_icms_node = root.find('.//cte:ICMS//cte:pICMS', ns)
            v_icms_node = root.find('.//cte:ICMS//cte:vICMS', ns)

            cst = cst_node.text.strip() if cst_node is not None else ''

            if cst in CST_ICMS_ZERO:
                # Isento / não tributado
                icms_r    = 0.0
                icms_taxa = 0.0
            else:
                icms_r = float(v_icms_node.text) if v_icms_node is not None else 0.0

                if p_icms_node is not None and p_icms_node.text:
                    try:
                        icms_taxa = float(p_icms_node.text) / 100.0
                    except ValueError:
                        icms_taxa = (icms_r / valor) if valor > 0 else 0.0
                else:
                    icms_taxa = (icms_r / valor) if valor > 0 else 0.0

            # ── volume (apenas M³, cUnid='00') ───────────────────────────────
            vol_m3 = 0.0
            unid_encontrada = ''

            for infQ in root.findall('.//cte:infQ', ns):
                c_unid  = infQ.find('cte:cUnid', ns)
                q_carga = infQ.find('cte:qCarga', ns)
                if c_unid is not None and c_unid.text == '00':
                    if q_carga is not None and q_carga.text:
                        try:
                            v = float(q_carga.text)
                            if v > 0:
                                vol_m3 = v
                                unid_encontrada = 'M3'
                                break
                        except ValueError:
                            pass
            # Unidades diferentes de M3 (mmbtu, kg etc.) → serviço de transporte puro,
            # volume não é contabilizado em m³ no CGR.

            return {
                'tipo':             'CT-e',
                'numero':           numero.text if numero is not None else 'N/A',
                'valor_total':      valor,
                'icms':             icms_r,
                'icms_taxa':        icms_taxa,
                'pis':              pis_r,
                'cofins':           cofins_r,
                'volume_total':     vol_m3,
                'unidade_volume':   unid_encontrada,
                'volume':           int(vol_m3),
            }
        except Exception as e:
            return {'erro': str(e)}

    # ── PDF / OCR ─────────────────────────────────────────────────────────────

    @staticmethod
    def parse_pdf_ocr(pdf_path: Path) -> Dict:
        """Extrai dados fiscais de um PDF (DANFE / DACTE / nota comercial).

        Estratégia de extração
        ----------------------
        1. Texto digital via pdfplumber (preferido).
        2. Fallback OCR (Tesseract) se o texto digital for vazio.
        3. Detecção automática do tipo de documento (DANFE ou DACTE).
        4. Extração posicional dos campos fiscais baseada no layout padrão.

        Campos retornados
        -----------------
        tipo, numero, valor_total, icms (R$), icms_taxa (decimal),
        pis (R$), cofins (R$), volume_total (m³), volume (int), fonte='OCR'.
        """

        # ── helpers ──────────────────────────────────────────────────────────
        def _extrair_texto(path: Path) -> str:
            texto = ''
            try:
                with pdfplumber.open(str(path)) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            texto += t + '\n'
                if not texto.strip() and OCR_ENABLED:
                    with pdfplumber.open(str(path)) as pdf:
                        for page in pdf.pages:
                            img = page.to_image(resolution=300).original
                            texto += pytesseract.image_to_string(img, lang='por') + '\n'
            except Exception:
                pass
            return texto

        def _parse_brl(s: str) -> float:
            """Converte '1.234.567,89' → 1234567.89"""
            s = s.strip().replace(' ', '')
            if ',' in s:
                s = s.replace('.', '').replace(',', '.')
            return float(s)

        def _find_brl(pattern: str, text: str, default: float = 0.0) -> float:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    return _parse_brl(m.group(1))
                except (ValueError, IndexError):
                    pass
            return default

        # ── extração de texto ─────────────────────────────────────────────
        texto = _extrair_texto(pdf_path)
        if not texto.strip():
            return {'erro': 'Não foi possível extrair texto do PDF'}

        txt_up = texto.upper()
        linhas  = texto.split('\n')

        # ── detecção do tipo ──────────────────────────────────────────────
        nome_up  = pdf_path.name.upper()
        is_dacte = ('DACTE' in txt_up or 'CT-E' in nome_up or 'CTE' in nome_up
                    or 'CT_E' in nome_up or 'CONHECIMENTO' in txt_up[:500])
        is_danfe = 'DANFE' in txt_up or 'NF-E' in txt_up[:300] or 'NOTA FISCAL' in txt_up[:500]

        valor    = 0.0
        icms_r   = 0.0
        icms_taxa = 0.0
        pis_r    = 0.0
        cofins_r = 0.0
        volume   = 0.0
        num      = 'N/A'

        # ══════ DANFE (NF-e) ══════════════════════════════════════════════
        if is_danfe and not is_dacte:
            tipo = 'NF-e'

            for i, linha in enumerate(linhas):
                lu = linha.upper()

                # Bloco "BASE DE CÁLCULO DO ICMS … VALOR TOTAL DOS PRODUTOS"
                if ('BASE' in lu and 'ICMS' in lu and 'VALOR' in lu
                        and 'TOTAL' in lu and 'PRODUTOS' in lu):
                    for j in range(i + 1, min(i + 3, len(linhas))):
                        nums = re.findall(r'[\d.]+,\d{2}', linhas[j])
                        if len(nums) >= 2:
                            try:
                                icms_r = _parse_brl(nums[1])
                            except (ValueError, IndexError):
                                pass
                            break

                # Bloco "VALOR DO FRETE … VALOR TOTAL DA NOTA"
                if ('VALOR' in lu and 'TOTAL' in lu
                        and 'NOTA' in lu and 'FRETE' in lu):
                    for j in range(i + 1, min(i + 3, len(linhas))):
                        nums = re.findall(r'[\d.]+,\d{2}', linhas[j])
                        if nums:
                            try:
                                valor = _parse_brl(nums[-1])
                            except (ValueError, IndexError):
                                pass
                            break

            if valor == 0.0:
                valor = _find_brl(
                    r'VALOR\s+TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)', txt_up)
            if icms_r == 0.0:
                icms_r = _find_brl(
                    r'VALOR\s+DO\s+ICMS\s*[:\-]?\s*([\d.,]+)', txt_up)

            # ICMS taxa: procurar "BASE DE CÁLCULO … % ICMS"
            m_taxa = re.search(
                r'ALIQ(?:UOTA)?\s*(?:DO\s*)?ICMS\s*[:\-]?\s*([\d,\.]+)\s*%', txt_up)
            if m_taxa:
                try:
                    icms_taxa = _parse_brl(m_taxa.group(1)) / 100.0
                except ValueError:
                    pass
            if icms_taxa == 0.0 and valor > 0:
                icms_taxa = icms_r / valor

            # Volume M3
            m_vol = re.search(r'M3\s+([\d.,]+)\s+([\d.,]+)', txt_up)
            if m_vol:
                try:
                    volume = _parse_brl(m_vol.group(1))
                except ValueError:
                    pass

            m_num = re.search(r'N[º°][.\s]*\s*0*(\d+)', texto)
            if m_num:
                num = m_num.group(1)

        # ══════ DACTE (CT-e) ══════════════════════════════════════════════
        elif is_dacte:
            tipo = 'CT-e'

            m_frete = re.search(r'Frete\s+valor\s+([\d.,]+)', texto)
            if m_frete:
                try:
                    valor = _parse_brl(m_frete.group(1))
                except ValueError:
                    pass

            if valor == 0.0:
                valor = _find_brl(
                    r'VALOR\s+(?:DA\s+PRESTA[ÇC][AÃ]O|TOTAL\s+DO\s+SERVI[CÇ]O)'
                    r'\s*[:\-]?\s*R?\$?\s*([\d.,]+)', txt_up)

            if valor == 0.0:
                todos_rs = []
                for m in re.finditer(r'R\$\s*([\d.,]+)', texto):
                    try:
                        todos_rs.append(_parse_brl(m.group(1)))
                    except ValueError:
                        pass
                if todos_rs:
                    valor = max(todos_rs)

            # ICMS
            m_icms_isento = re.search(r'40\s*-\s*ICMS\s+Isento', txt_up)
            if m_icms_isento:
                icms_r    = 0.0
                icms_taxa = 0.0
            else:
                icms_r = _find_brl(
                    r'VALOR\s+DO\s+ICMS\s*[:\-]?\s*([\d.,]+)', txt_up)
                if icms_r == 0.0:
                    m_icms_val = re.search(
                        r'ICMS[^0-9]+([\d.,]+)\s+([\d.,]+)', txt_up)
                    if m_icms_val:
                        try:
                            icms_r = _parse_brl(m_icms_val.group(2))
                        except ValueError:
                            pass

                # ICMS taxa: "% ICMS" ou "ALÍQUOTA ICMS"
                m_taxa = re.search(
                    r'(?:ALIQ(?:UOTA)?\s*(?:DO\s*)?ICMS|%\s*ICMS)\s*[:\-]?\s*([\d,\.]+)', txt_up)
                if m_taxa:
                    try:
                        icms_taxa = _parse_brl(m_taxa.group(1)) / 100.0
                    except ValueError:
                        pass
                if icms_taxa == 0.0 and valor > 0:
                    icms_taxa = icms_r / valor

            m_num = re.search(
                r'(?:NRO\.?\s*DOCUMENTO|N[ÚU]MERO)\s*[:.]?\s*(\d+)', txt_up)
            if m_num:
                num = m_num.group(1)
            else:
                m_num2 = re.search(r'CT-?E\s*[:\-]?\s*(\d+)', nome_up)
                if m_num2:
                    num = m_num2.group(1)

        # ══════ Nota comercial / outro ════════════════════════════════════
        else:
            tipo = 'NF-e'

            for padrao in [
                r'VALOR\s+TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)',
                r'VALOR\s+TOTAL\s*[:\-]?\s*([\d.,]+)',
                r'TOTAL\s*[:\-]?\s*([\d.,]+)',
            ]:
                valor = _find_brl(padrao, txt_up)
                if valor > 0:
                    break

            if valor == 0.0:
                todos = []
                for m in re.finditer(r'\b(\d{1,3}(?:\.\d{3})+,\d{2})\b', texto):
                    try:
                        todos.append(_parse_brl(m.group(1)))
                    except ValueError:
                        pass
                if todos:
                    valor = max(todos)

            icms_r = _find_brl(r'VALOR\s+DO\s+ICMS\s*[:\-]?\s*([\d.,]+)', txt_up)
            if icms_r == 0.0 and valor > 0:
                pass  # ICMS taxa permanece 0 (não tributado / isento)
            else:
                icms_taxa = icms_r / valor if valor > 0 else 0.0

            m_num = re.search(r'N[º°.]\s*(\d+)', texto)
            if m_num:
                num = m_num.group(1)

        resultado = {
            'tipo':         tipo,
            'numero':       num,
            'valor_total':  valor,
            'icms':         icms_r,
            'icms_taxa':    icms_taxa,
            'pis':          pis_r,
            'cofins':       cofins_r,
            'volume_total': volume,
            'volume':       int(volume),
            'fonte':        'OCR',
        }

        # Fallback IA (Gemini) apenas quando extração local vier fraca.
        # Mantém custo baixo e melhora casos em que OCR/layout não fecha.
        resultado_fraco = (
            resultado['valor_total'] <= 0.0
            or resultado['numero'] == 'N/A'
            or (resultado['tipo'] == 'NF-e' and resultado['icms'] <= 0.0)
        )

        return resultado