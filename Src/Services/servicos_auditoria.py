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
# Validada contra a planilha "Conta Gráfica e Apuração de Custos":
#
#   G (coluna "Compra R$ s/tributos") = F − ICMS − PIS(1,65%) − COFINS(7,60%)
#   G = (F − ICMS) × (1 − 0,0165 − 0,0760)
#   G = (F − ICMS) × (1 − PIS_COFINS_CGR_RATE)
#
#   CGR = Σ G = (Σ vNF − Σ vICMS) × (1 − PIS_COFINS_CGR_RATE)
#
# Verificação Dez/25: (112.441.134,15 − 12.440.114,91) × 0,9075 = 90.750.924,96 ✓
PIS_COFINS_CGR_RATE = 0.0925 # PIS 1,65% + COFINS 7,60% = 9,25%

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
    def calcular_cgr_liquido(valor_bruto: float, icms: float) -> float:
        """Retorna o valor líquido de tributos de um documento para o CGR."""
        return (valor_bruto - icms) * (1.0 - PIS_COFINS_CGR_RATE)

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
        """Extrai valor total de um PDF fiscal (NF-e/CT-e) quando não há XML."""
        import pdfplumber # Import local para garantir disponibilidade
        
        # Consideramos PDF_ATIVADO implícito se chegou aqui através do UI
        
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
                            img = page.to_image(resolution=200).original
                            texto += pytesseract.image_to_string(img, lang='eng') + '\n'
            except Exception:
                pass
            return texto

        def _parse_brl(s: str) -> float:
            s = s.strip().replace(' ', '')
            if ',' in s:
                s = s.replace('.', '').replace(',', '.')
            return float(s)

        texto = _extrair_texto(pdf_path)
        txt_up = texto.upper()

        valor = 0.0

        for padrao in [
            r'VALOR\s+TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)',
            r'TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)',
            r'VALOR\s+TOTAL\s*[:\-]?\s*([\d.,]+)',
            r'TOTAL\s+GERAL\s*[:\-]?\s*([\d.,]+)',
            r'TOTAL\s*[:\-]?\s*([\d.,]+)',
        ]:
            m = re.search(padrao, txt_up)
            if m:
                try:
                    v = _parse_brl(m.group(1))
                    if v > 1.0:
                        valor = v
                        break
                except ValueError:
                    pass

        if valor == 0.0:
            todos_brl = []
            for m in re.finditer(r'R\$\s*([\d.,]+)', txt_up):
                try:
                    todos_brl.append(_parse_brl(m.group(1)))
                except ValueError:
                    pass
            if todos_brl:
                valor = max(todos_brl)

        if valor == 0.0:
            todos_num = []
            for m in re.finditer(r'\b(\d{1,3}(?:\.\d{3})+,\d{2})\b', txt_up):
                try:
                    todos_num.append(_parse_brl(m.group(1)))
                except ValueError:
                    pass
            if todos_num:
                valor = max(todos_num)

        num = 'N/A'
        for padrao in [r'N[Oº°\.\s]*\.*\s*(\d{6,})', r'NF\s*[:\-]?\s*(\d+)',
                       r'CT-?E\s*[:\-]?\s*(\d+)', r'DANFE.*?(\d{6,})']:
            m = re.search(padrao, txt_up)
            if m:
                num = m.group(1)
                break

        nome_up = pdf_path.name.upper()
        if 'CT-E' in nome_up or 'CTE' in nome_up or 'CT_E' in nome_up:
            tipo = 'CT-e'
        else:
            tipo = 'NF-e'

        return {
            'tipo': tipo,
            'numero': num,
            'valor_total': valor,
            'icms': 0.0,
            'pis': 0.0,
            'cofins': 0.0,
            'volume_total': 0.0,
            'volume': 0,
            'fonte': 'OCR',
        }