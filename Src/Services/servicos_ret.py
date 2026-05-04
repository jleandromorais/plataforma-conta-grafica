import os
import re
from pathlib import Path
from Src.infrastructure.ocr.ocr_pdf import read_pdf_text

# Taxa de câmbio EUR → BRL
TAXA_EUR_BRL = 6.0

# Alíquota PIS/COFINS usada no cálculo regulatório do EC
PIS_COFINS_RATE = 0.0925

# Mapeamento de palavras encontradas nas pastas → número do mês
_MESES_PATH: dict[str, int] = {
    'JANEIRO': 1,  'JAN': 1,
    'FEVEREIRO': 2,'FEV': 2,
    'MARÇO': 3,    'MARCO': 3, 'MAR': 3,
    'ABRIL': 4,    'ABR': 4,
    'MAIO': 5,     'MAI': 5,
    'JUNHO': 6,    'JUN': 6,
    'JULHO': 7,    'JUL': 7,
    'AGOSTO': 8,   'AGO': 8,
    'SETEMBRO': 9, 'SET': 9,
    'OUTUBRO': 10, 'OUT': 10,
    'NOVEMBRO': 11,'NOV': 11,
    'DEZEMBRO': 12,'DEZ': 12,
}

_MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _extrair_mes_caminho(caminho: str) -> tuple[int, int]:
    """
    Varre as partes do caminho em busca do nome de um mês (PT-BR).
    Retorna (mes_num 1-12, ano 4-digitos) ou (0, 0) se não encontrado.
    O ano é o primeiro número de 4 dígitos no caminho; fallback = ano atual.
    """
    from datetime import date
    partes = Path(caminho).parts
    # Juntos todos os tokens das pastas (ignora o arquivo final)
    tokens_pastas = []
    for parte in partes[:-1]:
        # Separa por espaço, hífen, underscore, ponto
        tokens_pastas.extend(re.split(r'[\s\-_\.]+', parte.upper()))

    mes_num = 0
    for token in tokens_pastas:
        if token in _MESES_PATH:
            mes_num = _MESES_PATH[token]
            break

    # Procura ano de 4 dígitos no caminho completo (ex: "2026")
    anos = re.findall(r'\b(20\d{2}|19\d{2})\b', caminho)
    ano = int(anos[0]) if anos else date.today().year

    return mes_num, ano


class RegrasRET:
    @staticmethod
    def identificar_tipo(caminho):
        partes = [p.upper() for p in Path(caminho).parts[:-1]]
        for p in reversed(partes):
            if 'EAT' in p: return 'EAT'
            if p == 'EC' or p.startswith('EC ') or p.startswith('EC_'): return 'EC'
            if 'PENALIDADE' in p:
                if 'DESPESA' in p: return 'Penalidades (Despesa)'
                if 'RECEITA' in p: return 'Penalidades (Receita)'
                return 'Penalidades'
            if re.fullmatch(r'TOP[\s_\-]?.*', p) or p == 'TOP': return 'TOP'
        return 'Outros'

    @staticmethod
    def extrair_empresa(caminho):
        nome = os.path.basename(caminho).upper()
        pasta_pai = Path(caminho).parent.name.upper()
        empresas_conhecidas = [
            'PETROBRAS', 'GALP', 'BRAVA', 'ENEVA', 'MASTERGAS',
            'PETRORECONCAVO', 'PETRO RECONCAVO', 'TAG', 'GEB',
            'ORIZON', 'VECTOR', 'AMBEV', 'ALPEK', 'CBA', 'CERVEJARIA', 
            'DEXCO', 'FIAT', 'GERDAU', 'GYPSUM', 'INDORAMA', 'INGREDION', 
            'KLABIN', 'M DIAS BRANCO', 'MONDELEZ', 'NISSIN', 'OWENS', 
            'ROCA', 'TERPHANE', 'VETRUS', 'COPERGAS',
        ]
        for empresa in empresas_conhecidas:
            if empresa in nome or empresa in pasta_pai:
                return empresa
        return 'N/A'

    @staticmethod
    def extrair_tipo_nota(caminho):
        nome = os.path.basename(caminho).upper()
        if re.search(r'D[ÉE]BITO', nome): return 'Débito'
        if re.search(r'CR[ÉE]DITO', nome): return 'Crédito'
        if 'NDPFP' in nome: return 'Débito'
        if re.search(r'\bND[\d\-\_]*', nome): return 'Débito'
        if re.search(r'\bNC[\d\-\_]*', nome): return 'Crédito'
        if re.search(r'\b(NFE|NF|DANFE|CT-?E)\b', nome): return 'NF'
        return 'N/A'

    @staticmethod
    def extrair_calc_exato(texto: str) -> float:
        m = re.search(
            r'((?:\d{1,3}(?:[.\s]\d{3})*|\d{4,})(?:,\d+)?)'   
            r'\s*[^\d\sxX×R]{0,6}\s*[xX×]\s*'                  
            r'R\$\s*((?:\d{4,}|\d{1,3}(?:[.\s]\d{3})*)(?:[,.]\d+)?)',  
            texto,
        )
        if not m: return 0.0
        try:
            vol  = float(m.group(1).replace(' ', '').replace('.', '').replace(',', '.'))
            taxa = float(m.group(2).replace(' ', '').replace('.', '').replace(',', '.'))
            if vol > 0 and taxa > 0:
                return vol * taxa
        except ValueError:
            pass
        return 0.0

    @staticmethod
    def calcular_ret(dados_processados):
        eat_docs    = [d for d in dados_processados if d['tipo_encargo'] == 'EAT']
        ec_docs     = [d for d in dados_processados if d['tipo_encargo'] == 'EC']
        outros_docs = [d for d in dados_processados if d['tipo_encargo'] not in ('EAT', 'EC')]

        eat_bruto     = sum(d['valor_total'] for d in eat_docs)
        ec_docs_total = sum(d['valor_total'] for d in ec_docs)

        ec  = eat_bruto * (1.0 - PIS_COFINS_RATE) + ec_docs_total
        ret = ec

        return {
            'eat_bruto':       eat_bruto,
            'eat_docs':        eat_docs,
            'ec_docs_total':   ec_docs_total,
            'ec_docs':         ec_docs,
            'outros_docs':     outros_docs,
            'ec':              ec,
            'ret':             ret,
            'pis_cofins_rate': PIS_COFINS_RATE,
        }

    @staticmethod
    def extrair_dados_pdf(caminho_pdf, log_callback=None):
        mes_num, ano_cam = _extrair_mes_caminho(caminho_pdf)
        mes_ref = f"{_MESES_ABREV[mes_num - 1]}/{ano_cam}" if mes_num else ""

        dados = {
            'arquivo': os.path.basename(caminho_pdf),
            'caminho': caminho_pdf,
            'tipo_encargo': RegrasRET.identificar_tipo(caminho_pdf),
            'empresa': RegrasRET.extrair_empresa(caminho_pdf),
            'nota_tipo': RegrasRET.extrair_tipo_nota(caminho_pdf),
            'numero_nd': '',
            'data_vencimento': '',
            'mes_ref': mes_ref,        # mês extraído do nome das pastas
            'valor_total': 0.0,
            'quantidade': 0.0,
            'valor_unitario': 0.0,
            'moeda_detectada': 'BRL',
            'valores_encontrados': [],
            'periodo_doc': '',
            'contrib_ec': 'OUTROS',
        }
        
        try:
            texto_completo, metodo = read_pdf_text(Path(caminho_pdf), lang="eng")
            if metodo == "OCR": dados["ocr_usado"] = True

            nd_match = re.search(r'ND\s*[:\-]?\s*(\d+)', texto_completo, re.IGNORECASE)
            if nd_match: dados['numero_nd'] = nd_match.group(1)

            data_match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', texto_completo)
            if data_match: dados['data_vencimento'] = data_match.group(1)

            padrao_brl = r'R\$\s*((?:\d{4,}|\d{1,3}(?:[.\s]\d{3})*)(?:,\d{2})?)'
            padrao_eur = r'€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
            padrao_gen = r'(?<![€$\d,])(\d{1,3}(?:[.\s]\d{3})+,\d{2})(?!\d)'
            padrao_small = r'(?<![€$\d,.])(\d{1,5},\d{2})(?!\d)'

            def _parse(s: str) -> 'float | None':
                try:
                    v = float(s.replace(' ', '').replace('.', '').replace(',', '.'))
                    return v if v > 0 else None
                except Exception:
                    return None

            valores_brl = [v for m in re.findall(padrao_brl, texto_completo) if (v := _parse(m)) is not None]
            valores_eur = [v for m in re.findall(padrao_eur, texto_completo) if (v := _parse(m)) is not None]

            if not valores_brl and not valores_eur:
                valores_brl = [v for m in re.findall(padrao_gen, texto_completo) if (v := _parse(m)) is not None]

            if not valores_brl and not valores_eur:
                valores_brl = [v for m in re.findall(padrao_small, texto_completo) if (v := _parse(m)) is not None and v >= 10]

            todos_brl = valores_brl + [v * TAXA_EUR_BRL for v in valores_eur]
            dados['valores_encontrados'] = todos_brl
            dados['moeda_detectada']     = 'EUR' if valores_eur and not valores_brl else 'BRL'

            if todos_brl:
                calc_exato = RegrasRET.extrair_calc_exato(texto_completo)
                if calc_exato > 0: dados['valor_total'] = calc_exato
                else: dados['valor_total'] = max(todos_brl)

                qt_match = re.search(r'(?:QT|Quantidade)[:\s]*(\d+(?:[.,]\d+)?)', texto_completo, re.IGNORECASE)
                if qt_match: dados['quantidade'] = float(qt_match.group(1).replace(',', '.'))
                if dados['quantidade'] > 0: dados['valor_unitario'] = dados['valor_total'] / dados['quantidade']

            _MESES = {
                'JANEIRO': 1, 'FEVEREIRO': 2, 'MARCO': 3, 'MARÇO': 3,
                'ABRIL': 4, 'MAIO': 5, 'JUNHO': 6, 'JULHO': 7,
                'AGOSTO': 8, 'SETEMBRO': 9, 'OUTUBRO': 10,
                'NOVEMBRO': 11, 'DEZEMBRO': 12,
            }
            per_match = re.search(r'(?:PERIODO|PER[IÍ]ODO)\s+\d+\s+[AÀ]\s+\d+\s+DE\s+([A-Z\u00C0-\u00FF]+)/(\d{4})', texto_completo.upper())
            if per_match:
                mes_nome = per_match.group(1).strip()
                mes_num = _MESES.get(mes_nome, 0)
                if mes_num: dados['periodo_doc'] = f"{mes_num:02d}/{per_match.group(2)}"

        except Exception as e:
            if log_callback: log_callback(f"Erro ao processar {caminho_pdf}: {e}")

        tipo  = dados['tipo_encargo']
        arq_u = dados['arquivo'].upper()
        if tipo == 'Penalidades (Receita)' and 'NDPFP' in arq_u: dados['contrib_ec'] = 'NDPFP'
        elif tipo == 'EAT' and 'OAC' in arq_u: dados['contrib_ec'] = 'EAT_OAC'
        elif tipo == 'Penalidades (Despesa)' and ('OAC' in arq_u or 'VARIA' in arq_u): dados['contrib_ec'] = 'PFP_DESP_OAC'
        elif tipo == 'EAT': dados['contrib_ec'] = 'EAT_ND'
        elif tipo == 'Penalidades (Despesa)': dados['contrib_ec'] = 'PFP_DESP_ND'
        elif tipo == 'TOP': dados['contrib_ec'] = 'TOP'

        return dados