import pandas as pd, glob, os, warnings
warnings.filterwarnings('ignore')
os.chdir(r'c:\Users\jose.demorais\Downloads\Plataforma\plataforma-conta-grafica')

PMPV = 2.1204  # R$/m3 - Dez/25

# NF Faturada
fat_file = glob.glob('NF Faturada*.xlsx')[0]
df_fat   = pd.read_excel(fat_file)
df_fat['Volume Faturado'] = pd.to_numeric(df_fat['Volume Faturado'], errors='coerce')

TERMOS_CONS = ['consumo', 'proprio', 'proprio', 'cons. proprio']
mask_cons = pd.Series([False]*len(df_fat), index=df_fat.index)
for col in df_fat.columns:
    if df_fat[col].dtype == object:
        serie = df_fat[col].astype(str).str.lower().str.strip()
        for t in TERMOS_CONS:
            mask_cons |= serie.str.contains(t, na=False, regex=False)

vol_fat       = df_fat.loc[~mask_cons, 'Volume Faturado'].sum()
vol_cons_prop = df_fat.loc[mask_cons,  'Volume Faturado'].sum()

# NF Devolucao
dev_file = glob.glob('NF devolu*.xlsx')[0]
df_dev   = pd.read_excel(dev_file)
col_dev  = [c for c in df_dev.columns if 'devolu' in c.lower()][0]
df_dev[col_dev] = pd.to_numeric(df_dev[col_dev], errors='coerce')
vol_dev  = df_dev[col_dev].sum()

# VF e CGF
vf  = vol_fat - vol_dev - vol_cons_prop
cgf = vf * PMPV

sep = "=" * 52
lin = "-" * 52
print(sep)
print(f"  (+) Faturado limpo    : {vol_fat:>18,.4f} m3")
print(f"  (-) Devolucoes        : {vol_dev:>18,.4f} m3")
print(f"  (-) Consumo Proprio   : {vol_cons_prop:>18,.4f} m3")
print(lin)
print(f"  VF (Volume Final)     : {vf:>18,.4f} m3")
print(f"  x PMPV Dez/25         :       R$ {PMPV:.4f}/m3")
print(lin)
print(f"  CGF em R$             : R$ {cgf:>17,.2f}")
print(sep)
