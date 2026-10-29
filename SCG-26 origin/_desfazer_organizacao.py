"""Desfaz organizar_scg26.py pelo _organizacao_log.json: devolve cada pasta/arquivo ao lugar
e move os arquivos extraídos do zip de julho para _desfeito/ (não apaga).
Uso: python -I desfazer_organizacao.py <pasta SCG-26>"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(sys.argv[1])
log = json.loads((RAIZ / "_organizacao_log.json").read_text(encoding="utf-8"))
for p in reversed(log["passos"]):
    if p["tipo"] == "extraido":
        o = RAIZ / p["arquivo"]
        if o.exists():
            d = RAIZ / "_desfeito" / p["arquivo"]
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(o), str(d))
    else:
        o, d = RAIZ / p["para"], RAIZ / p["de"]
        if o.exists() and not d.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(o), str(d))
            print("voltou:", p["de"])
(RAIZ / "_organizacao_log.json").rename(RAIZ / "_organizacao_log.desfeito.json")
print("Desfeito. Arquivos extraídos foram para _desfeito/.")
