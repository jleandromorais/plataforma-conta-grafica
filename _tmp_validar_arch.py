from pathlib import Path
import zipfile, shutil, openpyxl
from Src.Services.servicos_auditoria import RegrasAuditoria

root = Path(r"c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica")
arch = root / "Src" / "Arch"
excel = arch / "Conta Gráfica e Apuração de Custos (1).xlsx"
meses = [
    ("46. Outubro 2025.zip", "Out25"),
    ("47. Novembro 2025.zip", "Nov25"),
    ("48. Dezembro 2025.zip", "Dez25"),
]

wb = openpyxl.load_workbook(excel, data_only=True)

def excel_total(sheet):
    ws = wb[sheet]
    sf = sm = sn = so = 0.0
    for r in range(18, ws.max_row + 1):
        vf = ws[f"F{r}"].value
        vm = ws[f"M{r}"].value
        vn = ws[f"N{r}"].value
        vo = ws[f"O{r}"].value
        if isinstance(vf, (int, float)) and vf > 0:
            sf += float(vf)
        if isinstance(vm, (int, float)):
            sm += float(vm)
        if isinstance(vn, (int, float)):
            sn += float(vn)
        if isinstance(vo, (int, float)):
            so += float(vo)
    return sf - sm - sn - so

for zip_name, sheet in meses:
    zpath = arch / zip_name
    temp = root / "_tmp_zip_check" / zip_name.replace(".zip", "")
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zpath, "r") as zf:
        zf.extractall(temp)

    nf_dirs = [p for p in temp.rglob("*") if p.is_dir() and p.name.lower() == "notas fiscais"]
    pasta_nf = nf_dirs[0]

    xmls = list({p.resolve() for p in pasta_nf.rglob("*.xml")})
    pdfs = list({p.resolve() for p in pasta_nf.rglob("*.pdf")})

    pastas_com_xml = {p.parent for p in xmls}
    arquivos_pdf = [p for p in pdfs if p.parent not in pastas_com_xml]

    resultados = []
    for x in xmls:
        tipo = RegrasAuditoria.detectar_tipo_xml(x)
        d = RegrasAuditoria.parse_nfe(x) if tipo == "nfe" else RegrasAuditoria.parse_cte(x) if tipo == "cte" else None
        if not d or "erro" in d:
            continue
        # Simula correção da tela: empresa agregada no somatório
        resultados.append(("Múltiplas", d.get("tipo", "?"), str(d.get("numero", "N/A")), float(d.get("valor_total", 0.0)), float(d.get("icms_taxa", 0.0))))

    for p in arquivos_pdf:
        d = RegrasAuditoria.parse_pdf_ocr(p)
        if "erro" in d:
            continue
        resultados.append(("Múltiplas", d.get("tipo", "?"), str(d.get("numero", "N/A")), float(d.get("valor_total", 0.0)), float(d.get("icms_taxa", 0.0))))

    seen = set()
    uniq = []
    for r in resultados:
        k = (r[0], r[1], r[2])
        if k not in seen:
            seen.add(k)
            uniq.append(r)

    prog = sum(RegrasAuditoria.calcular_s_tributos(v, t) for _, _, _, v, t in uniq)
    ex = excel_total(sheet)
    print(f"[{sheet}] docs={len(uniq)} programa={prog:,.2f} excel={ex:,.2f} diff={prog-ex:,.2f}")

shutil.rmtree(root / "_tmp_zip_check", ignore_errors=True)
