import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple, List
import pdfplumber
import pytesseract
from dataclasses import dataclass

from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED, read_pdf_text

# ── Fórmula regulatória CGR ──────────────────────────────────────────────────
# Validada contra a planilha "Conta Gráfica e Apuração de Custos" (abas Out25/Nov25/Dez25):
#
#   CGR = (Σ valor_total[todos] − Σ ICMS[todos]) × (1 − PIS_RATE − COFINS_RATE)
#
#   PIS/COFINS incidem sobre base (valor − ICMS): taxas fixas regulatórias.
#   Todos os tipos de documento contribuem (NF-e, CT-e, etc.).
#
# Verificação:
#   Dez/25: (112.441.134,15 − 12.440.114,91) × 0,9075 = 90.750.924,96 ✓
#   Nov/25: (117.947.652,94 − 14.463.268,28) × 0,9075 = 93.912.079,08 ✓
#   Out/25: (121.625.390,74 − 14.842.587,78) × 0,9075 = 96.905.393,69 ✓
PIS_RATE = 0.0165
COFINS_RATE = 0.076
PIS_COFINS_RATE = PIS_RATE + COFINS_RATE  # 0.0925

@dataclass
class XMLItem:
    """Representa um item auditado de XML fiscal"""
    empresa: str
    tipo: str
    numero: str
    valor_total: float
    icms: float
    pis: float
    cofins: float
    volume: int
    status: str
    volume_total: float

class RegrasAuditoria:
    
    @staticmethod
    def calcular_cgr_liquido(valor_total: float, icms_total: float) -> float:
        """Calcula o CGR líquido.

        Args:
            valor_total: soma bruta de TODOS os docs (NF-e + CT-e + etc.).
            icms_total: soma de ICMS de todos os docs.
        """
        return (valor_total - icms_total) * (1.0 - PIS_COFINS_RATE)

    @staticmethod
    def detectar_tipo_xml(xml_path: Path) -> str:
        """Detecta se é NF-e ou CT-e pelo conteúdo"""
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                conteudo = f.read(500)  # Lê só o início
                if 'nfeProc' in conteudo or 'NFe' in conteudo:
                    return 'nfe'
                elif 'cteProc' in conteudo or 'CTe' in conteudo:
                    return 'cte'
        except:
            pass
        return 'desconhecido'

    @staticmethod
    def parse_nfe(xml_path: Path) -> Dict:
        """Extrai dados de uma NF-e."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

            numero     = root.find('.//nfe:ide/nfe:nNF', ns)
            valor_tag  = root.find('.//nfe:total/nfe:ICMSTot/nfe:vNF', ns)
            valor_ext  = root.find('.//nfe:total/nfe:vNFTot', ns)
            icms       = root.find('.//nfe:total/nfe:ICMSTot/nfe:vICMS', ns)
            pis        = root.find('.//nfe:total/nfe:ICMSTot/nfe:vPIS', ns)
            cofins     = root.find('.//nfe:total/nfe:ICMSTot/nfe:vCOFINS', ns)

            # Volume M3
            UNIDADES_M3 = {'M3', 'M³', 'M 3', 'M3.'}
            vol_m3 = 0.0
            for det in root.findall('.//nfe:det', ns):
                u_com = det.find('nfe:prod/nfe:uCom', ns)
                q_com = det.find('nfe:prod/nfe:qCom', ns)
                if u_com is not None and q_com is not None:
                    if u_com.text.strip().upper() in UNIDADES_M3:
                        try:
                            vol_m3 += float(q_com.text)
                        except Exception:
                            pass

            # Fallback 1: vol/qVol
            if vol_m3 == 0.0:
                for vol in root.findall('.//nfe:vol', ns):
                    q_vol = vol.find('nfe:qVol', ns)
                    if q_vol is not None and q_vol.text:
                        try:
                            vol_m3 += float(q_vol.text)
                        except Exception:
                            pass

            # Fallback 2: pesoL do <vol>
            if vol_m3 == 0.0:
                peso = root.find('.//nfe:vol/nfe:pesoL', ns)
                if peso is not None and peso.text:
                    try:
                        vol_m3 = float(peso.text)
                    except Exception:
                        pass

            valor = (float(valor_ext.text) if valor_ext is not None else
                     float(valor_tag.text) if valor_tag is not None else 0.0)

            return {
                'tipo': 'NF-e',
                'numero': numero.text if numero is not None else 'N/A',
                'valor_total': valor,
                'icms':   float(icms.text)   if icms   is not None else 0.0,
                'pis':    float(pis.text)    if pis    is not None else 0.0,
                'cofins': float(cofins.text) if cofins is not None else 0.0,
                'volume_total': vol_m3,
                'volume': int(vol_m3),  
            }
        except Exception as e:
            return {'erro': str(e)}

    @staticmethod
    def parse_cte(xml_path: Path) -> Dict:
        """Extrai dados de um CT-e."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            ns = {'cte': 'http://www.portalfiscal.inf.br/cte'}

            numero      = root.find('.//cte:ide/cte:nCT', ns)
            valor_total = root.find('.//cte:vPrest/cte:vTPrest', ns)
            icms        = root.find('.//cte:ICMS//cte:vICMS', ns)
            pis         = root.find('.//cte:vPIS', ns)
            cofins      = root.find('.//cte:vCOFINS', ns)

            vol_m3 = 0.0
            unid_encontrada = ''

            for infQ in root.findall('.//cte:infQ', ns):
                c_unid  = infQ.find('cte:cUnid', ns)
                q_carga = infQ.find('cte:qCarga', ns)
                if c_unid is not None and q_carga is not None and c_unid.text == '00':
                    try:
                        v = float(q_carga.text)
                        if v > 0:
                            vol_m3 = v
                            unid_encontrada = 'M3'
                            break
                    except Exception:
                        pass

            if vol_m3 == 0.0:
                for infQ in root.findall('.//cte:infQ', ns):
                    q_carga = infQ.find('cte:qCarga', ns)
                    c_unid  = infQ.find('cte:cUnid', ns)
                    tp_med  = infQ.find('cte:tpMed', ns)
                    if q_carga is not None:
                        try:
                            v = float(q_carga.text)
                            if v > 0:
                                vol_m3 = v
                                unid_encontrada = (tp_med.text if tp_med is not None else
                                                   c_unid.text if c_unid is not None else '?')
                                break
                        except Exception:
                            pass

            return {
                'tipo': 'CT-e',
                'numero': numero.text if numero is not None else 'N/A',
                'valor_total': float(valor_total.text) if valor_total is not None else 0.0,
                'icms':   float(icms.text)   if icms   is not None else 0.0,
                'pis':    float(pis.text)    if pis    is not None else 0.0,
                'cofins': float(cofins.text) if cofins is not None else 0.0,
                'volume_total': vol_m3,
                'unidade_volume': unid_encontrada,
                'volume': int(vol_m3),  
            }
        except Exception as e:
            return {'erro': str(e)}

    @staticmethod
    def parse_pdf_ocr(pdf_path: Path) -> Dict:
        """Extrai dados fiscais de um PDF (DANFE / DACTE / nota comercial).

        Estratégia de extração:
          1. Texto digital via pdfplumber (preferido).
          2. Fallback OCR (Tesseract) se o texto digital for vazio.
          3. Detecção automática do tipo de documento (DANFE ou DACTE).
          4. Extração posicional dos campos fiscais baseada no layout padrão.
        """
        import pdfplumber

        # ── helpers ───────────────────────────────────────────────────
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
            """Busca regex e retorna o primeiro grupo como float BRL."""
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    return _parse_brl(m.group(1))
                except (ValueError, IndexError):
                    pass
            return default

        # ── extração de texto ─────────────────────────────────────────
        texto = _extrair_texto(pdf_path)
        if not texto.strip():
            return {'erro': 'Não foi possível extrair texto do PDF'}

        txt_up = texto.upper()
        linhas = texto.split('\n')

        # ── detecção do tipo ──────────────────────────────────────────
        nome_up = pdf_path.name.upper()
        is_dacte = ('DACTE' in txt_up or 'CT-E' in nome_up or 'CTE' in nome_up
                    or 'CT_E' in nome_up or 'FRETE' in txt_up.split('\n')[0]
                    or 'CONHECIMENTO' in txt_up[:500])
        is_danfe = 'DANFE' in txt_up or 'NF-E' in txt_up[:300] or 'NOTA FISCAL' in txt_up[:500]

        valor = 0.0
        icms = 0.0
        pis = 0.0
        cofins = 0.0
        volume = 0.0
        num = 'N/A'

        if is_danfe and not is_dacte:
            # ══════ DANFE (NF-e) ══════════════════════════════════════
            tipo = 'NF-e'

            # Layout padrão DANFE: a linha de cabeçalho "CÁLCULO DO IMPOSTO"
            # é seguida por labels e depois uma linha de valores numéricos.
            #
            # Padrão encontrado nos DANFEs reais:
            #   "BASE DE CÁLCULO DO ICMS  VALOR DO ICMS  BASE...ST  VALOR...ST  VALOR TOTAL DOS PRODUTOS"
            #   "69.132,27                14.172,11       0,00      0,00        69.132,27"
            #   "VALOR DO FRETE  VALOR DO SEGURO  VALOR DO DESCONTO  OUTRAS DESPESAS  VALOR DO IPI  VALOR TOTAL DA NOTA"
            #   "0,00            0,00             0,00               0,00             0,00           69.132,27"

            # Estratégia: procurar a linha do cabeçalho e a próxima linha com números
            for i, linha in enumerate(linhas):
                lu = linha.upper()
                # Bloco "CÁLCULO DO IMPOSTO" — linha de BC ICMS / VALOR ICMS / ... / VL TOTAL PRODUTOS
                if 'BASE' in lu and 'ICMS' in lu and 'VALOR' in lu and 'TOTAL' in lu and 'PRODUTOS' in lu:
                    # Próxima linha com números = os valores
                    for j in range(i + 1, min(i + 3, len(linhas))):
                        nums = re.findall(r'[\d.]+,\d{2}', linhas[j])
                        if len(nums) >= 2:
                            try:
                                # Ordem: BC_ICMS, ICMS, BC_ST, ICMS_ST, VL_PRODUTOS
                                icms = _parse_brl(nums[1])
                            except (ValueError, IndexError):
                                pass
                            break

                # Bloco "VALOR DO FRETE / ... / VALOR TOTAL DA NOTA"
                if 'VALOR' in lu and 'TOTAL' in lu and 'NOTA' in lu and 'FRETE' in lu:
                    for j in range(i + 1, min(i + 3, len(linhas))):
                        nums = re.findall(r'[\d.]+,\d{2}', linhas[j])
                        if nums:
                            try:
                                # Último valor na linha = VALOR TOTAL DA NOTA
                                valor = _parse_brl(nums[-1])
                            except (ValueError, IndexError):
                                pass
                            break

            # Fallback: regex direto
            if valor == 0.0:
                valor = _find_brl(r'VALOR\s+TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)', txt_up)
            if icms == 0.0:
                icms = _find_brl(r'VALOR\s+DO\s+ICMS\s*[:\-]?\s*([\d.,]+)', txt_up)

            # Volume M3 — linha de produtos com "M3"
            m_vol = re.search(r'M3\s+([\d.,]+)\s+([\d.,]+)', txt_up)
            if m_vol:
                try:
                    volume = _parse_brl(m_vol.group(1))
                except ValueError:
                    pass

            # Número da NF — "Nº. 0000144" / "Nº 144" / "N. 144"
            m_num = re.search(r'N[º°][.\s]*\s*0*(\d+)', texto)
            if m_num:
                num = m_num.group(1)

        elif is_dacte:
            # ══════ DACTE (CT-e) ══════════════════════════════════════
            tipo = 'CT-e'

            # Layout padrão DACTE:
            #   "Frete valor XXXXX,XX" ou "Frete peso ... R$ XXXXX,XX"
            #   ICMS aparece na linha "40 - ICMS Isento..." ou em bloco ICMS
            #   Valor da prestação: "R$ XXX.XXX,XX" perto de "Frete valor"

            # Valor da prestação (vTPrest): procurar "Frete valor" ou o total da prestação
            m_frete = re.search(r'Frete\s+valor\s+([\d.,]+)', texto)
            if m_frete:
                try:
                    valor = _parse_brl(m_frete.group(1))
                except ValueError:
                    pass

            if valor == 0.0:
                # Fallback: "VALOR DA PRESTAÇÃO" ou "VALOR TOTAL"
                valor = _find_brl(r'VALOR\s+(?:DA\s+PRESTA[ÇC][AÃ]O|TOTAL\s+DO\s+SERVI[CÇ]O)\s*[:\-]?\s*R?\$?\s*([\d.,]+)', txt_up)

            if valor == 0.0:
                # Fallback: procurar R$ com o maior valor
                todos_rs = []
                for m in re.finditer(r'R\$\s*([\d.,]+)', texto):
                    try:
                        todos_rs.append(_parse_brl(m.group(1)))
                    except ValueError:
                        pass
                if todos_rs:
                    valor = max(todos_rs)

            # ICMS do CT-e
            # Padrão "40 - ICMS Isento" com valores 0,00
            m_icms_isento = re.search(r'40\s*-\s*ICMS\s+Isento', txt_up)
            if m_icms_isento:
                icms = 0.0
            else:
                icms = _find_brl(r'VALOR\s+DO\s+ICMS\s*[:\-]?\s*([\d.,]+)', txt_up)
                if icms == 0.0:
                    # Bloco ICMS com valores
                    m_icms_val = re.search(r'ICMS[^0-9]+([\d.,]+)\s+([\d.,]+)', txt_up)
                    if m_icms_val:
                        try:
                            icms = _parse_brl(m_icms_val.group(2))
                        except ValueError:
                            pass

            # Número do CT-e
            m_num = re.search(r'(?:NRO\.?\s*DOCUMENTO|N[ÚU]MERO)\s*[:.]?\s*(\d+)', txt_up)
            if m_num:
                num = m_num.group(1)
            else:
                m_num2 = re.search(r'CT-?E\s*[:\-]?\s*(\d+)', nome_up)
                if m_num2:
                    num = m_num2.group(1)

        else:
            # ══════ Nota comercial / outro ════════════════════════════
            tipo = 'NF-e'  # default

            # Tentar extrair valor total genérico
            for padrao in [
                r'VALOR\s+TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)',
                r'VALOR\s+TOTAL\s*[:\-]?\s*([\d.,]+)',
                r'TOTAL\s*[:\-]?\s*([\d.,]+)',
            ]:
                valor = _find_brl(padrao, txt_up)
                if valor > 0:
                    break

            if valor == 0.0:
                # Pegar o maior valor BRL do texto
                todos = []
                for m in re.finditer(r'\b(\d{1,3}(?:\.\d{3})+,\d{2})\b', texto):
                    try:
                        todos.append(_parse_brl(m.group(1)))
                    except ValueError:
                        pass
                if todos:
                    valor = max(todos)

            m_num = re.search(r'N[º°.]\s*(\d+)', texto)
            if m_num:
                num = m_num.group(1)

        return {
            'tipo': tipo,
            'numero': num,
            'valor_total': valor,
            'icms': icms,
            'pis': pis,
            'cofins': cofins,
            'volume_total': volume,
            'volume': int(volume),
            'fonte': 'OCR',
        }