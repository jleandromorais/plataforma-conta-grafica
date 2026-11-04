"""Copia uma pasta de notas para um caminho curto e encurta os nomes longos.

O navegador (e o Windows) não leem arquivos cujo caminho completo passa de 260
caracteres. Os XMLs da Petrobras vêm com nomes como
"Nota Fiscal [NF.ITEM]-NOFI_NR_NOTA_FISCAL[000000046]-...-NFIT_NR_ITEM[10].xml"
e, dentro de "Downloads\\SCG-26\\RPV - ...\\CGR\\01 jan-26 ...", estouram o limite:
a tela mostra "Não consegui ler o arquivo".

O que o script faz:
- COPIA (nunca move nem apaga) a pasta de origem para o destino, mantendo as
  subpastas (mês e empresa), que é o que o sistema usa para achar o período e a
  empresa;
- renomeia o padrão da Petrobras para "NF 46 serie 43 item 10.xml";
- encurta qualquer outro nome que ainda deixe o caminho longo demais;
- não sobrescreve: se o nome já existe no destino, acrescenta " (2)", " (3)"...

O número, o valor e o emitente da nota são lidos de dentro do XML/PDF, não do
nome, então renomear não muda o resultado da Auditoria.

Uso (PowerShell, na pasta plataforma-conta-grafica):
    python scripts\\organizar_notas.py "C:\\...\\SCG-26\\RPV - Recuperação do Preço de Venda\\CGR"
    python scripts\\organizar_notas.py "<origem>" --destino C:\\Notas
    python scripts\\organizar_notas.py "<origem>" --simular      (só mostra o que faria)

Sem copiar, renomeando na própria pasta só o que passa do limite (com log):
    python scripts\\organizar_notas.py "C:\\...\\SCG-26 origin" --no-lugar --simular
    python scripts\\organizar_notas.py "C:\\...\\SCG-26 origin" --no-lugar
    python scripts\\organizar_notas.py "C:\\...\\SCG-26 origin" --desfazer
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

LIMITE = 240  # folga abaixo dos 260 do Windows
PADRAO_PETROBRAS = re.compile(
    r"NOFI_NR_NOTA_FISCAL\[\s*0*(\d+)\s*\].*?NOFI_NR_SERIE_DOC\[\s*([^\]]*?)\s*\]"
    r"(?:.*?NFIT_NR_ITEM\[\s*0*(\d+)\s*\])?",
    re.IGNORECASE,
)
IGNORAR = {"desktop.ini", "thumbs.db", ".ds_store"}
# Palavras que as regras leem no nome do arquivo: (como volta no nome, trechos que a regra procura).
PALAVRAS_DO_NOME = (
    ("CTe", ("ct-e", "cte", "ct_e")),                  # Auditoria: DACTE
    ("devolucao", ("devolu", "devolv")),               # Auditoria: devolução abate o CGR
    ("TOP", ("top",)),                                 # Conciliação: TOP não recuperável
    ("atualizada", ("atualiz",)),                      # Conciliação: original × atualizada
    ("cancelado", ("cancelad",)),                      # Conciliação: ND cancelada
)


def _longo(p: Path) -> str:
    """Caminho com prefixo \\\\?\\ no Windows: lê arquivos acima de 260 caracteres."""
    s = str(p.resolve())
    if os.name == "nt" and not s.startswith("\\\\?\\"):
        return "\\\\?\\" + s
    return s


def nome_curto(nome: str) -> str:
    """Nome da Petrobras → "NF 46 serie 43 item 10.xml"; os outros ficam iguais."""
    base, ext = os.path.splitext(nome)
    m = PADRAO_PETROBRAS.search(base)
    if not m:
        return nome
    numero, serie, item = m.groups()
    partes = [f"NF {numero}"]
    if serie:
        partes.append(f"serie {serie}")
    if item:
        partes.append(f"item {item}")
    return " ".join(partes) + ext


def caber(pasta: Path, nome: str) -> str:
    """Encurta `nome` até `pasta/nome` caber em LIMITE, mantendo a extensão e um
    trecho do hash do nome original para não colidir com outro encurtado.
    O sistema lê algumas palavras do nome (Auditoria: CT-e, devolução;
    Conciliação: TOP, atualizada, cancelado): se o corte apagar uma delas, ela
    volta no fim do nome."""
    if len(str(pasta / nome)) <= LIMITE:
        return nome
    base, ext = os.path.splitext(nome)
    original = base.lower()
    marca = "~" + hashlib.sha1(nome.encode("utf-8")).hexdigest()[:6]
    presentes = [p for p, chaves in PALAVRAS_DO_NOME if any(k in original for k in chaves)]
    sobra = LIMITE - len(str(pasta)) - 1 - len(ext) - len(marca) - sum(len(p) + 1 for p in presentes)
    if sobra < 8:
        raise ValueError(f"A pasta de destino é longa demais para os arquivos: {pasta}")
    curto = base[:sobra].rstrip(" .")
    perdidas = [
        palavra for palavra, chaves in PALAVRAS_DO_NOME
        if palavra in presentes and not any(k in curto.lower() for k in chaves)
    ]
    return curto + marca + "".join(" " + p for p in perdidas) + ext


def livre(pasta: Path, nome: str, usados: set[str]) -> str:
    """Nome que ainda não existe no destino (nem foi usado nesta execução)."""
    base, ext = os.path.splitext(nome)
    candidato, n = nome, 1
    while candidato.lower() in usados or (pasta / candidato).exists():
        n += 1
        candidato = f"{base} ({n}){ext}"
    usados.add(candidato.lower())
    return candidato


def organizar(origem: Path, destino: Path, simular: bool) -> dict:
    raiz_destino = destino / origem.name
    contagem = {"copiados": 0, "renomeados": 0, "ignorados": 0}
    usados_por_pasta: dict[Path, set[str]] = {}

    for atual, pastas, arquivos in os.walk(_longo(origem)):
        pastas.sort()
        rel = Path(atual.replace("\\\\?\\", "")).resolve().relative_to(origem.resolve())
        pasta_dest = raiz_destino / rel
        usados = usados_por_pasta.setdefault(pasta_dest, set())
        for nome in sorted(arquivos):
            if nome.lower() in IGNORAR:
                contagem["ignorados"] += 1
                continue
            novo = livre(pasta_dest, caber(pasta_dest, nome_curto(nome)), usados)
            if novo != nome:
                contagem["renomeados"] += 1
                print(f"  {rel / nome}\n    -> {novo}")
            contagem["copiados"] += 1
            if not simular:
                pasta_dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(os.path.join(atual, nome), pasta_dest / novo)
    contagem["destino"] = str(raiz_destino)
    return contagem


LOG = "_renomear_log.json"


def renomear_no_lugar(raiz: Path, simular: bool) -> int:
    """Renomeia, dentro da própria pasta, só os arquivos cujo caminho passa do
    limite. Grava de/para em `raiz/_renomear_log.json` para `--desfazer`."""
    raiz = raiz.resolve()  # nome completo (sem "JOSE~1"), como o os.walk devolve
    passos = []
    for atual, pastas, arquivos in os.walk(_longo(raiz)):
        pastas.sort()
        pasta = Path(atual.replace("\\\\?\\", ""))
        usados = {n.lower() for n in arquivos}
        for nome in sorted(arquivos):
            if len(str(pasta / nome)) <= LIMITE:
                continue
            usados.discard(nome.lower())
            try:
                novo = livre(pasta, caber(pasta, nome_curto(nome)), usados)
            except ValueError:
                print(f"  ⚠ Não dá para encurtar (a pasta já é longa demais): {pasta / nome}")
                usados.add(nome.lower())
                continue
            de, para = (pasta / nome).relative_to(raiz), (pasta / novo).relative_to(raiz)
            print(f"  {de}\n    -> {novo}")
            passos.append({"de": de.as_posix(), "para": para.as_posix()})
            if not simular:
                os.rename(os.path.join(atual, nome), os.path.join(atual, novo))
    if passos and not simular:
        caminho_log = raiz / LOG
        historico = json.loads(caminho_log.read_text(encoding="utf-8")) if caminho_log.exists() else []
        historico.append({"quando": datetime.now().isoformat(timespec="seconds"), "passos": passos})
        caminho_log.write_text(json.dumps(historico, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(passos)


def desfazer(raiz: Path) -> int:
    """Volta os nomes da última execução registrada em `_renomear_log.json`."""
    raiz = raiz.resolve()
    caminho_log = raiz / LOG
    if not caminho_log.exists():
        print(f"Não há {LOG} em {raiz}: nada para desfazer.")
        return 0
    historico = json.loads(caminho_log.read_text(encoding="utf-8"))
    ultima = historico.pop()
    for p in reversed(ultima["passos"]):
        atual, original = raiz / p["para"], raiz / p["de"]
        if os.path.exists(_longo(atual)) and not os.path.exists(_longo(original)):
            os.rename(_longo(atual), _longo(original))
            print("voltou:", p["de"])
    if historico:
        caminho_log.write_text(json.dumps(historico, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        caminho_log.unlink()
    return len(ultima["passos"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Copia a pasta de notas para um caminho curto e encurta nomes longos.")
    ap.add_argument("origem", help="Pasta com as notas (ex.: a pasta CGR ou a de um mês)")
    ap.add_argument("--destino", default=r"C:\Notas", help=r"Onde criar a cópia (padrão: C:\Notas)")
    ap.add_argument("--no-lugar", action="store_true",
                    help="Não copia: renomeia na própria pasta só os arquivos de caminho longo (com log)")
    ap.add_argument("--desfazer", action="store_true", help="Volta os nomes da última execução com --no-lugar")
    ap.add_argument("--simular", action="store_true", help="Só mostra o que faria, sem copiar nem renomear")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    origem = Path(args.origem)
    if not origem.is_dir():
        print(f"Pasta não encontrada: {origem}")
        return 1
    if args.desfazer:
        print(f"{desfazer(origem)} nome(s) restaurado(s).")
        return 0
    if args.no_lugar:
        print(("SIMULAÇÃO: nada será renomeado.\n" if args.simular else "") + f"Pasta: {origem}\n")
        n = renomear_no_lugar(origem, args.simular)
        print(f"\n{n} arquivo(s) {'a renomear' if args.simular else 'renomeados'}."
              + ("" if args.simular or not n else f" Para voltar: --desfazer (log em {origem / LOG})"))
        return 0
    destino = Path(args.destino)
    if (destino / origem.name).resolve() == origem.resolve():
        print("O destino é a própria pasta de origem. Escolha outro --destino.")
        return 1

    print(("SIMULAÇÃO: nada será copiado.\n" if args.simular else "") + f"Origem:  {origem}\nDestino: {destino / origem.name}\n")
    r = organizar(origem, destino, args.simular)
    print(f"\n{r['copiados']} arquivo(s) {'a copiar' if args.simular else 'copiados'}, "
          f"{r['renomeados']} com nome encurtado, {r['ignorados']} ignorado(s).")
    if not args.simular:
        print(f"Pronto. No site, escolha a pasta: {r['destino']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
