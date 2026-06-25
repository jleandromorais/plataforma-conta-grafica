import pandas as pd, glob, os, warnings
warnings.filterwarnings('ignore')
os.chdir(r'c:\Users\jose.demorais\Downloads\Plataforma\plataforma-conta-grafica')

arq = glob.glob('Mem*ria de C*lculo.xlsx')[0]
xl  = pd.ExcelFile(arq)
print("Abas:", xl.sheet_names)

# Composicao
aba_comp = xl.sheet_names[0]
df_comp = pd.read_excel(xl, sheet_name=aba_comp, header=None)
print(f"\n=== {aba_comp} - ultimas 25 linhas ===")
print(df_comp.tail(25).to_string())

# PMPV
aba_pmpv = xl.sheet_names[1]
df_pmpv = pd.read_excel(xl, sheet_name=aba_pmpv, header=None)
print(f"\n=== {aba_pmpv} - ultimas 30 linhas ===")
print(df_pmpv.tail(30).to_string())
