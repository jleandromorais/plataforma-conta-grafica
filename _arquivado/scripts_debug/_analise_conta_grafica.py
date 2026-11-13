import glob, sys, openpyxl
sys.stdout.reconfigure(encoding='utf-8')

f = [x for x in glob.glob('*.xlsx') if 'Conta' in x and 'Calculador' not in x][0]
wb_v = openpyxl.load_workbook(f, data_only=True)
wb_f = openpyxl.load_workbook(f, data_only=False)
ws_v = wb_v['Dez25']
ws_f = wb_f['Dez25']

# ── Cabeçalhos de todas as colunas da linha 17 ──────────────────────
print('CABEÇALHOS LINHA 17 (todas as colunas com conteúdo):')
for c in range(1, 30):
    v = ws_v.cell(17, c).value
    if v is not None:
        letra = openpyxl.utils.get_column_letter(c)
        print(f'  {letra} (col {c:2d}): {v}')

# ── Primeira linha de dados não-zero para ver os valores reais ───────
print()
print('='*80)
print('PRIMEIRA LINHA COM VALOR > 0 (linha 18 a 50):')
for r in range(18, 50):
    gv = ws_v.cell(r, 7).value
    if gv and float(gv) > 100:
        print(f'\nLinha {r}:')
        for c in range(1, 25):
            v  = ws_v.cell(r, c).value
            formula = ws_f.cell(r, c).value
            letra = openpyxl.utils.get_column_letter(c)
            if v is not None:
                try:
                    vf = f'{float(v):>18,.2f}'
                except:
                    vf = f'{str(v):>18}'
                print(f'  {letra:>2} (col {c:2d}): {vf}  [formula: {str(formula)[:60]}]')
        break

# ── Somas por coluna para Dez25 (G18:G182 e M18:P182) ───────────────
print()
print('='*80)
print('SOMAS POR COLUNA (linhas 18-182):')
somas = {}
for r in range(18, 183):
    for c in range(5, 22):  # F até U
        v = ws_v.cell(r, c).value
        if v is not None:
            try:
                somas[c] = somas.get(c, 0.0) + float(v)
            except: pass

for c in sorted(somas):
    letra = openpyxl.utils.get_column_letter(c)
    cab = ws_v.cell(17, c).value or ''
    if abs(somas[c]) > 100:
        print(f'  {letra} (col {c:2d}) [{str(cab):30}]: {somas[c]:>18,.2f}')

# ── Verificar: F - M - N - O - P == G ? ─────────────────────────────
print()
print('='*80)
print('VERIFICAÇÃO: G = F - SUM(M:P)')
print(f'  F (com tributos)   = {somas.get(6, 0):>18,.2f}')
for c in range(13, 18):
    letra = openpyxl.utils.get_column_letter(c)
    cab = ws_v.cell(17, c).value or ''
    print(f'  {letra} [{cab:20}]  = {somas.get(c, 0):>18,.2f}')
total_impostos = sum(somas.get(c, 0) for c in range(13, 18))
g_calc = somas.get(6, 0) - total_impostos
g_real = somas.get(7, 0)
print(f'  {"─"*50}')
print(f'  F - SUM(M:P) calculado = {g_calc:>18,.2f}')
print(f'  G real (planilha)      = {g_real:>18,.2f}')
print(f'  Diferença              = {g_calc - g_real:>+18,.2f}')
print()
print(f'  ALVO CGR AX13          = {90750924.96:>18,.2f}')
print(f'  G real (planilha)      = {g_real:>18,.2f}')
print(f'  Diferença              = {g_real - 90750924.96:>+18,.2f}')
