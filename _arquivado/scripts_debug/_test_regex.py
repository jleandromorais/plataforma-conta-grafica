import re

padrao_brl = r'R\$\s*((?:\d{4,}|\d{1,3}(?:[.\s]\d{3})*)(?:,\d{2})?)'

def _parse(s):
    return float(s.replace(' ', '').replace('.', '').replace(',', '.'))

casos = [
    ('R$139789,99',   139789.99),
    ('R$ 26.524,62',  26524.62),
    ('R$ 2 524,85',   2524.85),
    ('R$104.638,26',  104638.26),
    ('R$ 0,16',       0.16),
    ('R$ 4,54',       4.54),
    ('R$11.283,15',   11283.15),
    ('R$139.789,99',  139789.99),
    ('R$ 142.029,44', 142029.44),
]

print('TESTE DO REGEX CORRIGIDO:')
todos_ok = True
for texto, esperado in casos:
    matches = re.findall(padrao_brl, texto)
    resultado = max((_parse(m) for m in matches), default=0.0)
    ok = abs(resultado - esperado) < 0.01
    status = "OK   " if ok else "FALHA"
    print(f"  {status} | {texto:25s} -> {resultado:>12,.2f}  (esperado: {esperado:,.2f})")
    if not ok:
        todos_ok = False

print()
print("TODOS OK!" if todos_ok else "FALHAS DETECTADAS!")
