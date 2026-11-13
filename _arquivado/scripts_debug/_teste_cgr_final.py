import zipfile, glob, sys, os, io, re
from xml.etree import ElementTree as ET
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\jose.demorais\Downloads\Plataforma\plataforma-conta-grafica'
zpath = glob.glob(base + r'\CGR*.zip')[0]
ALVO = 90750924.96

NS_NFE = '{http://www.portalfiscal.inf.br/nfe}'
NS_CTE = '{http://www.portalfiscal.inf.br/cte}'

try:
    import pdfplumber, pytesseract
    candidatos = [
        r'C:\Users\jose.demorais\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.join(os.environ.get('LOCALAPPDATA',''), 'Programs','Tesseract-OCR','tesseract.exe'),
    ]
    tess = next((p for p in candidatos if os.path.exists(p)), None)
    if tess: pytesseract.pytesseract.tesseract_cmd = tess
    OCR_OK = tess is not None
    print(f'pdfplumber OK  |  OCR: {"ATIVO" if OCR_OK else "INATIVO"}')
except ImportError as e:
    OCR_OK = False; print(f'AVISO: {e}')

def parse_brl(s):
    s = s.strip().replace(' ', '')
    if ',' in s: s = s.replace('.', '').replace(',', '.')
    return float(s)

def ocr_pdf_bytes(data: bytes, nome: str) -> float:
    texto = ''
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: texto += t + '\n'
        if not texto.strip() and OCR_OK:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    img = page.to_image(resolution=200).original
                    texto += pytesseract.image_to_string(img, lang='eng') + '\n'
    except Exception as e:
        print(f'  ERRO ao ler {nome}: {e}')
        return 0.0

    txt_up = texto.upper()

    # Padrões de valor total (prioridade decrescente)
    for padrao in [
        r'VALOR\s+TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)',
        r'TOTAL\s+DA\s+NOTA\s*[:\-]?\s*([\d.,]+)',
        r'VALOR\s+TOTAL\s*[:\-]?\s*([\d.,]+)',
        r'TOTAL\s+GERAL\s*[:\-]?\s*([\d.,]+)',
    ]:
        m = re.search(padrao, txt_up)
        if m:
            try:
                v = parse_brl(m.group(1))
                if v > 1.0: return v
            except: pass

    # Maior valor no formato XX.XXX.XXX,XX
    todos = []
    for m in re.finditer(r'\b(\d{1,3}(?:\.\d{3})+,\d{2})\b', txt_up):
        try: todos.append(parse_brl(m.group(1)))
        except: pass
    if todos: return max(todos)
    return 0.0

def get_xml(root, *tags):
    for t in tags:
        for ns in [NS_NFE, NS_CTE, '']:
            el = root.find(f'.//{ns}{t}')
            if el is not None and el.text:
                try: return float(el.text.strip())
                except: pass
    return 0.0

# ── Processar ZIP ──────────────────────────────────────────────
resultados = []
orizon_ocr = []

with zipfile.ZipFile(zpath) as z:
    todos = z.namelist()
    xmls = [n for n in todos if n.upper().endswith('.XML')]
    pdfs = [n for n in todos if n.upper().endswith('.PDF')]

    # Empresas que têm pelo menos 1 XML
    empresas_com_xml = {n.split('/')[1] for n in xmls if '/' in n}

    # 1️⃣ XMLs (todas as empresas que têm XML)
    for nome in xmls:
        emp = nome.split('/')[1] if '/' in nome else '?'
        with z.open(nome) as fh:
            root = ET.parse(fh).getroot()
        tag = ET.tostring(root, encoding='unicode')[:200].lower()
        tipo = 'NF-e' if 'nfe' in tag else ('CT-e' if 'cte' in tag else '?')
        valor = get_xml(root, 'vNF','vNFe','vNFTot') or get_xml(root, 'vTPrest','vRec')
        resultados.append({'emp': emp, 'tipo': tipo, 'valor': valor, 'fonte': 'XML'})

    # 2️⃣ PDFs SOMENTE de empresas que NÃO têm nenhum XML → OCR
    pdfs_orfaos = [n for n in pdfs
                   if n.split('/')[1] not in empresas_com_xml and '/' in n]
    print(f'\nPDFs de empresas SEM XML ({len(pdfs_orfaos)}):')
    for nome in pdfs_orfaos:
        emp = nome.split('/')[1]
        arq = nome.rsplit('/',1)[-1]
        with z.open(nome) as fh:
            data = fh.read()
        valor = ocr_pdf_bytes(data, arq)
        print(f'  {emp}/{arq}  →  R$ {valor:,.2f}')
        resultados.append({'emp': emp, 'tipo': 'NF-e', 'valor': valor, 'fonte': 'OCR'})
        orizon_ocr.append(valor)

# ── Totais ────────────────────────────────────────────────────
def fmt(v):
    return f'{v:,.2f}'.replace(',','X').replace('.',',').replace('X','.')

soma_nfe = sum(r['valor'] for r in resultados if r['tipo'] == 'NF-e')
soma_cte = sum(r['valor'] for r in resultados if r['tipo'] == 'CT-e')
soma_ocr = sum(orizon_ocr)
total    = soma_nfe + soma_cte

por_emp = defaultdict(float)
for r in resultados:
    por_emp[r['emp']] += r['valor']

print()
print('SOMA POR EMPRESA:')
for emp in sorted(por_emp):
    print(f'  {emp:<20}  R$ {fmt(por_emp[emp]):>20}')

print()
print('='*57)
print(f'  NF-e (XML + OCR)       R$ {fmt(soma_nfe):>22}')
print(f'  CT-e (XML)             R$ {fmt(soma_cte):>22}')
if soma_ocr:
    print(f'  -- subtotal OCR        R$ {fmt(soma_ocr):>22}')
print(f'  {"─"*53}')
print(f'  TOTAL GERAL            R$ {fmt(total):>22}')
print(f'  ALVO AX13              R$ {fmt(ALVO):>22}')
dif = total - ALVO
marca = '  <<< BINGO!' if abs(dif) < 1.0 else f'  dif = R$ {dif:+,.2f}'.replace(',','X').replace('.',',').replace('X','.')
print(f'  DIFERENÇA              R$ {fmt(dif):>22}{marca}')
print('='*57)
