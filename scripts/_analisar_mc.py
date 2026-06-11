import pandas as pd, glob, os, warnings
warnings.filterwarnings('ignore')
os.chdir(r'c:\Users\jose.demorais\Downloads\Plataforma\plataforma-conta-grafica')

arq = glob.glob('Mem*ria de C*lculo.xlsx')[0]
xl  = pd.ExcelFile(arq)
df  = pd.read_excel(xl, sheet_name='PMPV', header=None)

# --- Identificar colunas de meses ---
first_header_row = None
meses_cols = {}
PT = {'Jan':'Jan','Feb':'Fev','Mar':'Mar','Apr':'Abr','May':'Mai',
      'Jun':'Jun','Jul':'Jul','Aug':'Ago','Sep':'Set','Oct':'Out',
      'Nov':'Nov','Dec':'Dez'}

for ri in range(min(5, len(df))):
    for ci in range(len(df.columns)):
        c = df.iloc[ri, ci]
        if hasattr(c, 'strftime'):
            first_header_row = ri
            for ci2 in range(len(df.columns)):
                c2 = df.iloc[ri, ci2]
                if hasattr(c2, 'strftime'):
                    p   = c2.strftime('%b/%y').split('/')
                    lbl = PT.get(p[0], p[0]) + '/' + p[1]
                    meses_cols[ci2] = (lbl, c2)
            break
    if first_header_row is not None:
        break

print('Meses encontrados:', {ci: lbl for ci,(lbl,_) in meses_cols.items()})
first_month_col = min(meses_cols.keys())

# --- Parsear empresas para cada mês ---
empresas = {}   # empresa -> {col_idx -> {mol, trans, log, volume}}

empresa_atual = None
for ri in range(len(df)):
    col1 = df.iloc[ri, 1]
    col2 = df.iloc[ri, 2]
    fm   = df.iloc[ri, first_month_col]
    col1s = str(col1).strip() if pd.notna(col1) else ''
    col2s = str(col2).strip() if pd.notna(col2) else ''
    is_date = pd.notna(fm) and hasattr(fm, 'strftime')

    if (not col1s or col1s == 'nan') and col2s and col2s != 'nan' and is_date:
        empresa_atual = col2s
        if empresa_atual not in empresas:
            empresas[empresa_atual] = {ci: {'mol':0,'trans':0,'log':0,'volume':0}
                                       for ci in meses_cols}
        continue

    if empresa_atual is None:
        continue

    for ci in meses_cols:
        v = df.iloc[ri, ci]
        vf = float(v) if pd.notna(v) and str(v).strip() not in ('','nan') else 0.0
        if col1s == 'A':   empresas[empresa_atual][ci]['mol']    = vf
        elif col1s == 'B': empresas[empresa_atual][ci]['trans']  = vf
        elif col1s == 'C' and vf: empresas[empresa_atual][ci]['log'] = vf
        elif col1s == 'E': empresas[empresa_atual][ci]['volume'] = vf

# --- Calcular PMPV por mês ---
print()
for ci, (lbl, _) in sorted(meses_cols.items()):
    soma_custo = soma_vol = 0.0
    print(f'=== {lbl} ===')
    for emp, meses_d in empresas.items():
        d = meses_d[ci]
        vol  = d['volume']
        preco = d['mol'] + d['trans'] + d['log']
        custo = vol * preco
        if vol > 0:
            print(f'  {emp:<35} vol={vol:>12,.0f}  preco={preco:.4f}  custo={custo:>15,.2f}')
        soma_vol   += vol
        soma_custo += custo
    pmpv = soma_custo / soma_vol if soma_vol else 0
    print(f'  {"TOTAL":<35} vol={soma_vol:>12,.0f}')
    print(f'  >>> PMPV = R$ {pmpv:.4f} / m3')
    print()
