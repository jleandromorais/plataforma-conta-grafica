"""
Script temporário: extrai valor de cada PDF de Dezembro 2025
e testa todas as combinações para encontrar a que dá 154.768,56.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))

import pdfplumber

# ── Tesseract ────────────────────────────────────────────────────────────────
try:
    import pytesseract
    from PIL import Image
    _CANDS = [
        r'C:\Users\jose.demorais\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    _tp = next((p for p in _CANDS if os.path.exists(p)), None)
    if _tp:
        pytesseract.pytesseract.tesseract_cmd = _tp
    OCR_ON = _tp is not None
except ImportError:
    pytesseract = None
    OCR_ON = False

ALVO = 154_768.562025          # valor exato do Excel (AX16 = EC)
PASTA = (
    r"c:\Users\jose.demorais\Downloads\Plataforma\plataforma-conta-grafica"
    r"\_dados_referencia\Penalidades\Penalidades\48. Dezembro 2025"
)

# ── helpers ──────────────────────────────────────────────────────────────────
def _parse(s: str) -> float:
    s = s.replace(' ', '').replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0

def extrair_valor(caminho: str) -> float:
    """Extrai o maior valor monetário do PDF (R$ ou EUR→BRL)."""
    texto = ""
    try:
        with pdfplumber.open(caminho) as pdf:
            for pg in pdf.pages:
                t = pg.extract_text() or ""
                if not t.strip() and OCR_ON:
                    img = pg.to_image(resolution=200).original
                    t = pytesseract.image_to_string(img, lang='eng')
                texto += t + "\n"
    except Exception as e:
        print(f"  ERRO ao abrir {os.path.basename(caminho)}: {e}")
        return 0.0

    candidatos: list[float] = []

    # R$ explícito — testa \d{4,} antes de \d{1,3} para capturar "R$139789,99"
    for m in re.finditer(r'R\$\s*((?:\d{4,}|\d{1,3}(?:[.\s]\d{3})*)(?:,\d{2})?)', texto):
        candidatos.append(_parse(m.group(1)))

    # EUR → BRL  (taxa padrão usada no código: 5,xxxx — mas buscamos o padrão €)
    for m in re.finditer(r'€\s*([\d]{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)', texto):
        val_eur = _parse(m.group(1))
        # taxa do modulo_ret (última conhecida ~5.78... mas vamos armazenar EUR mesmo
        # para o usuário ver; aqui multiplicamos por 1 para não distorcer)
        candidatos.append(val_eur)

    # Padrão genérico com milhar (. ou espaço) + vírgula decimal
    for m in re.finditer(r'(?<![€$\d,])(\d{1,3}(?:[.\s]\d{3})+,\d{2})(?!\d)', texto):
        candidatos.append(_parse(m.group(1)))

    # Valores pequenos sem separador de milhar (ex: 37,88)
    for m in re.finditer(r'(?<![€$\d,.\-])(\d{1,5},\d{2})(?!\d)', texto):
        v = _parse(m.group(1))
        if v >= 10:
            candidatos.append(v)

    if not candidatos:
        return 0.0
    return max(candidatos)

# ── coleta ────────────────────────────────────────────────────────────────────
def eh_nf(nome: str) -> bool:
    n = nome.upper()
    if re.search(r'D[ÉE]BITO', n): return False
    if re.search(r'CR[ÉE]DITO', n): return False
    if 'NDPFP' in n: return False
    if re.search(r'\bND[\d\-\_]*', n): return False
    if re.search(r'\bNC[\d\-\_]*', n): return False
    if re.search(r'\b(NFE|NF|DANFE|CT-?E)\b', n): return True
    return False

grupos: dict[str, list[tuple[str, float]]] = {
    "EAT_OAC":       [],
    "EAT_ND":        [],
    "PFP_DESP_OAC":  [],
    "PFP_DESP_ND":   [],
    "NDPFP":         [],
    "TOP":           [],
}

print("=" * 70)
print("EXTRAÇÃO DE VALORES – DEZEMBRO 2025")
print("=" * 70)

for root, dirs, files in os.walk(PASTA):
    # pular subpastas Notas Fiscais
    dirs[:] = [d for d in dirs if 'NOTAS FISCAIS' not in d.upper() and 'NOTA FISCAL' not in d.upper()]
    for arq in sorted(files):
        if not arq.lower().endswith('.pdf'):
            continue
        if eh_nf(arq):
            print(f"  [NF-SKIP] {arq}")
            continue

        caminho = os.path.join(root, arq)
        partes   = [p.upper() for p in os.path.relpath(caminho, PASTA).split(os.sep)[:-1]]
        pasta_immediata = partes[-1] if partes else ""

        val = extrair_valor(caminho)

        # ── classifica ──────────────────────────────────────────────────────
        # TOP tem prioridade sobre qualquer pasta que contenha "RECEITA"
        if 'TOP' in pasta_immediata or 'TOPNREC' in arq.upper():
            grp = 'TOP'
        elif 'EAT' in pasta_immediata:
            if 'OAC' in arq.upper():
                grp = 'EAT_OAC'
            else:
                grp = 'EAT_ND'
        elif 'DESPESA' in pasta_immediata or 'DESPESA' in ' '.join(partes):
            if 'OAC' in arq.upper() or 'VARIA' in arq.upper():
                grp = 'PFP_DESP_OAC'
            else:
                grp = 'PFP_DESP_ND'
        elif 'NDPFP' in arq.upper() or 'RECEITA' in pasta_immediata:
            grp = 'NDPFP'
        else:
            grp = 'EAT_ND'   # fallback

        grupos[grp].append((arq, val))
        print(f"  [{grp:15s}] {arq:<55s}  R$ {val:>12,.2f}")

print()
print("=" * 70)
print("RESUMO POR GRUPO")
print("=" * 70)
totais: dict[str, float] = {}
for grp, itens in grupos.items():
    s = sum(v for _, v in itens)
    totais[grp] = s
    print(f"  {grp:<15s}  qtd={len(itens):2d}  total = R$ {s:>12,.2f}")

print()
print("=" * 70)
print("BUSCA DA FÓRMULA  (alvo = R$ 154.768,562025)")
print("=" * 70)

eat_oac      = totais['EAT_OAC']
eat_nd       = totais['EAT_ND']
pfp_desp_oac = totais['PFP_DESP_OAC']
pfp_desp_nd  = totais['PFP_DESP_ND']
ndpfp        = totais['NDPFP']
top          = totais['TOP']

# Separa AMBEV TOP do total TOP
top_ambev = next((v for n,v in grupos['TOP'] if 'AMBEV' in n.upper()), 0.0)
top_outros = top - top_ambev

formulas = {
    "NDPFP":
        ndpfp,
    "NDPFP - EAT_OAC":
        ndpfp - eat_oac,
    "NDPFP - PFP_DESP_OAC":
        ndpfp - pfp_desp_oac,
    "NDPFP - EAT_OAC - PFP_DESP_OAC":
        ndpfp - eat_oac - pfp_desp_oac,
    "NDPFP - EAT_OAC - PFP_DESP_OAC - TOP_AMBEV":
        ndpfp - eat_oac - pfp_desp_oac - top_ambev,
    "NDPFP - EAT_OAC - PFP_DESP_OAC - TOP_TODOS":
        ndpfp - eat_oac - pfp_desp_oac - top,
    "NDPFP - EAT_OAC - PFP_DESP_TODOS":
        ndpfp - eat_oac - pfp_desp_oac - pfp_desp_nd,
    "NDPFP - EAT_OAC - PFP_DESP_TODOS - TOP_AMBEV":
        ndpfp - eat_oac - pfp_desp_oac - pfp_desp_nd - top_ambev,
    "NDPFP - EAT_OAC - PFP_DESP_TODOS - TOP_TODOS":
        ndpfp - eat_oac - pfp_desp_oac - pfp_desp_nd - top,
    "NDPFP - EAT_TODOS - PFP_DESP_OAC":
        ndpfp - eat_oac - eat_nd - pfp_desp_oac,
    "NDPFP - EAT_TODOS - PFP_DESP_TODOS":
        ndpfp - eat_oac - eat_nd - pfp_desp_oac - pfp_desp_nd,
    "NDPFP + TOP - EAT_OAC - PFP_DESP_OAC":
        ndpfp + top - eat_oac - pfp_desp_oac,
    "NDPFP + TOP - EAT_TODOS - PFP_DESP_TODOS":
        ndpfp + top - eat_oac - eat_nd - pfp_desp_oac - pfp_desp_nd,
    "NDPFP + TOP_AMBEV - EAT_OAC - PFP_DESP_OAC":
        ndpfp + top_ambev - eat_oac - pfp_desp_oac,
}

melhor_nome  = ""
melhor_dif   = float('inf')

for nome, resultado in formulas.items():
    dif = abs(resultado - ALVO)
    marca = " ◄◄◄ MATCH !!!" if dif < 0.01 else (f" (dif = {dif:+.4f})" if dif < 200 else "")
    print(f"  {nome:<55s}  R$ {resultado:>12,.2f}{marca}")
    if dif < melhor_dif:
        melhor_dif   = dif
        melhor_nome  = nome

print()
print(f"  MELHOR APROXIMACAO -> {melhor_nome}")
print(f"  Diferenca          -> R$ {melhor_dif:,.4f}")
print(f"  Alvo               -> R$ {ALVO:,.6f}")
print("=" * 70)

# ── Verificação de hipótese: qual NDPFP precisa valer +9,20 para fechar? ─────
print()
print("=" * 70)
print("HIPOTESE: qual arquivo com +9,20 fecha a formula NDPFP-EAT_OAC-PFP_DESP_OAC-TOP_AMBEV?")
print("=" * 70)
eat_oac2      = sum(v for _, v in grupos['EAT_OAC'])
pfp_oac2      = sum(v for _, v in grupos['PFP_DESP_OAC'])
top_ambev2    = next((v for n, v in grupos['TOP'] if 'AMBEV' in n.upper()), 0.0)
ndpfp_itens   = grupos['NDPFP']
ndpfp_total2  = sum(v for _, v in ndpfp_itens)

resultado_base = ndpfp_total2 - eat_oac2 - pfp_oac2 - top_ambev2
print(f"  Formula base (com valores OCR): R$ {resultado_base:,.2f}")
print(f"  Alvo:                           R$ {ALVO:,.2f}")
print(f"  Deficit a preencher:            R$ {ALVO - resultado_base:,.4f}")
print()
print("  Se o valor correto de cada NDPFP fosse:")
for nome, val in sorted(ndpfp_itens, key=lambda x: x[1]):
    # quanto precisaria ser para fechar sozinho (todos os outros iguais)
    val_necessario = val + (ALVO - resultado_base)
    print(f"    {nome:<55s}  OCR={val:>10,.2f}  necessario={val_necessario:>10,.2f}")
print("=" * 70)
