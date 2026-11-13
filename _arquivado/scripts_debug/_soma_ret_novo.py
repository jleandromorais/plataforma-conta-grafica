"""Calcula soma dos PDFs do novo zip RET (EAT + EC)."""
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
import pdfplumber

try:
    import pytesseract
    _tp = next((p for p in [
        r'C:\Users\jose.demorais\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    ] if os.path.exists(p)), None)
    if _tp: pytesseract.pytesseract.tesseract_cmd = _tp
    OCR_ON = _tp is not None
except ImportError:
    pytesseract = None; OCR_ON = False

BASE = glob.glob(r'c:\Users\jose.demorais\Downloads\Plataforma\plataforma-conta-grafica\_dados_referencia\RET_novo\*')[0]

padrao_brl = r'R\$\s*((?:\d{4,}|\d{1,3}(?:[.\s]\d{3})*)(?:,\d{2})?)'

def _parse(s):
    return float(s.replace(' ','').replace('.','').replace(',','.'))

def _extrair_calc_exato(texto):
    m = re.search(
        r'((?:\d{1,3}(?:[.\s]\d{3})*|\d{4,})(?:,\d+)?)'
        r'\s*[^\d\sxX\xd7R]{0,6}\s*[xX\xd7]\s*'
        r'R\$\s*((?:\d{4,}|\d{1,3}(?:[.\s]\d{3})*)(?:[,.]\d+)?)',
        texto,
    )
    if not m: return 0.0
    try:
        vol  = _parse(m.group(1))
        taxa = float(m.group(2).replace(' ','').replace('.','').replace(',','.'))
        return vol * taxa if vol > 0 and taxa > 0 else 0.0
    except ValueError:
        return 0.0

def extrair_valor(caminho):
    texto = ""
    with pdfplumber.open(caminho) as pdf:
        for pg in pdf.pages:
            t = pg.extract_text() or ""
            if not t.strip() and OCR_ON:
                img = pg.to_image(resolution=200).original
                t = pytesseract.image_to_string(img, lang='eng')
            texto += t + "\n"

    exato = _extrair_calc_exato(texto)
    if exato > 0: return exato, True

    cands = [_parse(m) for m in re.findall(padrao_brl, texto) if m]
    if not cands:
        padrao_gen = r'(?<![€$\d,])(\d{1,3}(?:[.\s]\d{3})+,\d{2})(?!\d)'
        cands = [_parse(m) for m in re.findall(padrao_gen, texto)]
    if not cands:
        padrao_sml = r'(?<![€$\d,.])(\d{1,5},\d{2})(?!\d)'
        cands = [v for m in re.findall(padrao_sml, texto) if (v := _parse(m)) >= 10]
    return (max(cands) if cands else 0.0), False

SEP = "=" * 65

print(SEP)
print(f"  SOMA - RET NOVO ZIP")
print(f"  Pasta raiz: {os.path.basename(BASE)}")
print(SEP)

totais = {}
for root, dirs, files in os.walk(BASE):
    dirs.sort()
    for arq in sorted(files):
        if not arq.lower().endswith('.pdf'): continue
        caminho = os.path.join(root, arq)
        pasta   = os.path.basename(root)

        val, exato = extrair_valor(caminho)
        fonte = "exato" if exato else "  pdf"

        if pasta not in totais:
            totais[pasta] = []
            print(f"\n  [{pasta}]")
        totais[pasta].append(val)
        print(f"    [{fonte}] {arq:<52s}  {val:>18.6f}")

print()
print(SEP)
ret_total = 0.0
for pasta, vals in totais.items():
    s = sum(vals)
    ret_total += s
    print(f"  {pasta:<15s} ({len(vals)} PDF) =  {s:>18.6f}")
print(f"  {'-'*53}")
print(f"  RET TOTAL              =  {ret_total:>18.6f}")
print(SEP)
