from pathlib import Path
from backend.etl.extractors.xml_extractor import extrair_xml

pasta = Path(r"Z:\.0Pastas _para_automacao\SCG\SCG - Dezembro 2025\RPV - Recuperação do Preço de Venda\CGR - Custo do Gás Realizado")

# Lista os XMLs que existem nessa pasta
xmls = list(pasta.rglob("*.xml"))
print(f"Encontrados: {len(xmls)} XMLs")

# Testa com o primeiro XML
if xmls:
    resultado = extrair_xml(xmls[0])
    print(f"Arquivo: {xmls[0].name}")
    print(f"Resultado: {resultado}")
else:
    print("Nenhum XML encontrado nessa pasta.")