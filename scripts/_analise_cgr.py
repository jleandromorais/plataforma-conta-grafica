import zipfile, glob, sys, io, re
from xml.etree import ElementTree as ET
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\jose.demorais\Downloads\Plataforma\plataforma-conta-grafica'
zpath = glob.glob(base + r'\CGR*.zip')[0]
ALVO = 90750924.96

NS_NFE = '{http://www.portalfiscal.inf.br/nfe}'
NS_CTE = '{http://www.portalfiscal.inf.br/cte}'

def get(root, *tags):
    for t in tags:
        for ns in [NS_NFE, NS_CTE, '']:
            el = root.find(f'.//{ns}{t}')
            if el is not None and el.text:
                try: return float(el.text.strip())
                except: pass
    return 0.0

# ── Somar XMLs ────────────────────────────────────────────────────
dados_xml = []
with zipfile.ZipFile(zpath) as z:
    # Lista de empresas e arquivos
    todos = z.namelist()
    xmls = [n for n in todos if n.upper().endswith('.XML')]
    pdfs = [n for n in todos if n.upper().endswith('.PDF')]

    # Empresas com PDF mas sem XML
    pasta_com_xml = set(n.split('/')[1] for n in xmls if '/' in n)
    pasta_com_pdf = set(n.split('/')[1] for n in pdfs if '/' in n)
    sem_xml = pasta_com_pdf - pasta_com_xml
    print(f'Pastas COM PDF mas SEM XML: {sem_xml}')

    for nome in xmls:
        emp = nome.split('/')[1] if '/' in nome else '?'
        with z.open(nome) as fh:
            root = ET.parse(fh).getroot()
        tag = ET.tostring(root, encoding='unicode')[:300].lower()
        tipo = 'NF-e' if 'nfe' in tag else ('CT-e' if 'cte' in tag else '?')
        vnf    = get(root, 'vNF', 'vNFe', 'vNFTot')
        vtpres = get(root, 'vTPrest', 'vRec')
        vicms  = get(root, 'vICMS')
        vpis   = get(root, 'vPIS')
        vcof   = get(root, 'vCOFINS')
        data   = ''
        for t in ['dhEmi','dEmi']:
            for ns in [NS_NFE, NS_CTE,'']:
                el = root.find(f'.//{ns}{t}')
                if el is not None and el.text:
                    data = el.text[:10]; break
            if data: break
        dados_xml.append({'emp': emp,'tipo': tipo,'data': data,
                          'vnf': vnf,'vtpres': vtpres,'vicms': vicms,
                          'vpis': vpis,'vcof': vcof})

    # ── Ler PDFs da Orizon ────────────────────────────────────────
    print('\nPDFs da Orizon:')
    orizon_valor = 0.0
    for nome in pdfs:
        if 'Orizon' in nome or 'orizon' in nome.lower():
            print(f'  {nome}')
            try:
                import pdfplumber
                with z.open(nome) as fh:
                    data_bytes = fh.read()
                with pdfplumber.open(io.BytesIO(data_bytes)) as pdf:
                    texto = '\n'.join(p.extract_text() or '' for p in pdf.pages)
                print(f'  --- TEXTO (trecho) ---')
                for linha in texto.split('\n')[:40]:
                    if any(c.isdigit() for c in linha):
                        print(f'    {linha}')
                # tentar extrair valor total
                # Padrão brasileiro R$ XX.XXX.XXX,XX ou TOTAL R$ XX
                matches = re.findall(r'R\$\s*([\d.,]+)', texto)
                print(f'  Valores R$ encontrados: {matches[:10]}')
                # Maior valor provavelmente é o total
                valores = []
                for m in matches:
                    v = m.replace('.','').replace(',','.')
                    try: valores.append(float(v))
                    except: pass
                if valores:
                    maximo = max(valores)
                    print(f'  Maior valor = R$ {maximo:,.2f}')
                    orizon_valor += maximo
            except Exception as e:
                print(f'  ERRO ao ler PDF: {e}')

# ── Resultados ────────────────────────────────────────────────────
soma_nfe     = sum(r['vnf']   for r in dados_xml if r['tipo'] == 'NF-e')
soma_cte     = sum(r['vtpres'] for r in dados_xml if r['tipo'] == 'CT-e')
soma_icms    = sum(r['vicms'] for r in dados_xml)
soma_pis_cof = sum(r['vpis'] + r['vcof'] for r in dados_xml)

print(f'\n{"="*60}')
print(f'SOMA NF-e (vNF)                  : R$ {soma_nfe:>18,.2f}')
print(f'SOMA CT-e (vTPrest)              : R$ {soma_cte:>18,.2f}')
print(f'SOMA vICMS                       : R$ {soma_icms:>18,.2f}')
print(f'SOMA vPIS+COFINS                 : R$ {soma_pis_cof:>18,.2f}')
print(f'Orizon PDF (maior valor p/NF)    : R$ {orizon_valor:>18,.2f}')
print(f'{"="*60}')
print(f'ALVO AX13                        : R$ {ALVO:>18,.2f}')

combos = [
    ('NF-e + Orizon',             soma_nfe + orizon_valor),
    ('NF-e + CT-e + Orizon',      soma_nfe + soma_cte + orizon_valor),
    ('NF-e - ICMS + Orizon',      soma_nfe - soma_icms + orizon_valor),
    ('NF-e - ICMS',               soma_nfe - soma_icms),
    ('NF-e - ICMS - PIS/COF',     soma_nfe - soma_icms - soma_pis_cof),
    ('NF-e + CT-e - ICMS',        soma_nfe + soma_cte - soma_icms),
]
print()
for nome, v in combos:
    dif = v - ALVO
    marca = '  <<< BINGO!' if abs(dif) < 1.0 else (f'  PERTO! dif=R${dif:+,.2f}' if abs(dif) < 100000 else f'  dif=R${dif:+,.2f}')
    print(f'  {nome:<40}  R$ {v:>18,.2f}{marca}'.replace(',','X').replace('.',',').replace('X','.'))
