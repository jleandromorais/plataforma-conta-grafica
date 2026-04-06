"""Diagnostico: texto completo dos PDFs sem XML."""
import sys, pdfplumber, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

meses = [
    ('48. Dezembro 2025', 90750924.96),
    ('47. Novembro 2025', 93912079.05),
    ('46. Outubro 2025',  96905393.68),
]

for mes_nome, alvo in meses:
    base = Path(f'_dados_referencia/Penalidades/Penalidades/{mes_nome}/Notas Fiscais')
    if not base.exists():
        continue
    for empresa_dir in sorted(base.iterdir()):
        if not empresa_dir.is_dir():
            continue
        xmls = list(empresa_dir.rglob('*.xml'))
        pdfs = list(empresa_dir.rglob('*.pdf'))
        if not xmls and pdfs:
            for pdf_path in pdfs:
                print(f'\n{"="*70}')
                print(f'{mes_nome} / {empresa_dir.name} / {pdf_path.name}')
                print(f'{"="*70}')
                with pdfplumber.open(str(pdf_path)) as pdf:
                    for i, page in enumerate(pdf.pages):
                        texto = page.extract_text() or ''
                        print(f'--- Pg {i+1} ---')
                        for line in texto.split('\n'):
                            # Mostrar linhas com numeros
                            if any(c.isdigit() for c in line):
                                print(f'  {line}')


