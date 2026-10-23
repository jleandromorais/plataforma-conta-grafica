"""Regrava CGR/CGF/RET/RP de cada mês com os valores da planilha oficial
(aba "Conta Gráfica" do Novo modelo Alexandre) e recalcula RPV e SCG.

Só grava os meses que diferem da planilha (> R$ 1); meses certos ficam
como estão. Apaga Out/2026, registro lixo sem CGR/CGF.

Sem --aplicar só mostra o que mudaria.

    # banco local (este computador)
    python scripts/corrigir_scg_da_planilha.py --local [--aplicar]

    # banco do site (pede a senha)
    python scripts/corrigir_scg_da_planilha.py --api https://plataforma-conta-grafica-production.up.railway.app/api --email voce@empresa.com [--aplicar]
"""
from __future__ import annotations

import argparse
import getpass
import glob
import sys
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
PERIODOS = [f"{MESES[m - 1]}/{a}" for a, m in
            [(2025, m) for m in range(7, 13)] + [(2026, m) for m in range(1, 10)]]
APAGAR = ["Out/2026"]
# Linhas da aba "Conta Gráfica"; coluna C = Jan/2022.
LINHAS = {"cgr": 13, "rp": 41, "ret": 42, "cgf": 43}
TOLERANCIA = 1.0  # R$ — centavos de arredondamento não justificam regravar


def valores_planilha(arquivo: Path) -> dict[str, dict[str, float]]:
    ws = openpyxl.load_workbook(arquivo, data_only=True)["Conta Gráfica"]
    saida = {}
    for p in PERIODOS:
        mes, ano = MESES.index(p[:3]) + 1, int(p[4:])
        col = 3 + (ano - 2022) * 12 + (mes - 1)
        data = ws.cell(10, col).value
        if not data or (data.year, data.month) != (ano, mes):
            raise SystemExit(f"Coluna {col} da planilha não é {p} (achei {data}).")
        vals = {k: ws.cell(r, col).value for k, r in LINHAS.items()}
        if vals["cgr"] is None:
            print(f"{p}: sem CGR na planilha, ignorado")
            continue
        saida[p] = {k: float(v or 0) for k, v in vals.items()}
    return saida


class Local:
    def __init__(self):
        from Src.Services.servicos_scg import ServicosSCG
        self.s = ServicosSCG()

    def gravado(self, p):
        return self.s.buscar_dados_periodo(p)

    def salvar(self, p, v):
        return self.s.salvar_e_calcular(p, v["cgr"], v["cgf"], v["ret"], v["rp"])

    def apagar(self, p):
        self.s.apagar_periodo(p)


class Api:
    def __init__(self, url: str, email: str):
        import requests
        self.url, self.http = url.rstrip("/"), requests.Session()
        r = self.http.post(f"{self.url}/auth/login",
                           json={"email": email, "senha": getpass.getpass("Senha: ")}, timeout=30)
        r.raise_for_status()
        self.http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    def gravado(self, p):
        r = self.http.get(f"{self.url}/scg", params={"periodo": p}, timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def salvar(self, p, v):
        r = self.http.post(f"{self.url}/scg/salvar", json={"periodo": p, **v}, timeout=30)
        r.raise_for_status()
        return r.json()

    def apagar(self, p):
        self.http.delete(f"{self.url}/scg", params={"periodo": p}, timeout=30).raise_for_status()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    alvo = ap.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--local", action="store_true")
    alvo.add_argument("--api")
    ap.add_argument("--email")
    ap.add_argument("--planilha", type=Path,
                    default=next(iter(glob.glob(str(RAIZ / "Novo modelo Alexandre*.xlsx"))), None))
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    if a.api and not a.email:
        ap.error("--api exige --email")

    planilha = valores_planilha(a.planilha)
    banco = Local() if a.local else Api(a.api, a.email)
    acao = "GRAVADO" if a.aplicar else "mudaria"

    for p, novo in planilha.items():
        atual = banco.gravado(p) or {}
        difs = {k: (atual.get(k, 0.0), novo[k]) for k in novo
                if abs((atual.get(k) or 0.0) - novo[k]) > TOLERANCIA}
        if not difs:
            print(f"{p}: ok")
            continue
        print(f"{p}: {acao} " + "; ".join(f"{k} {de:,.2f} -> {para:,.2f}" for k, (de, para) in difs.items()))
        if a.aplicar:
            print(f"    SCG = {banco.salvar(p, novo)['scg']:,.2f}")

    for p in APAGAR:
        atual = banco.gravado(p)
        if atual is None:
            continue
        if atual.get("cgr") or atual.get("cgf"):
            print(f"{p}: tem CGR/CGF, NÃO apagado")
            continue
        print(f"{p}: {'APAGADO' if a.aplicar else 'seria apagado'}")
        if a.aplicar:
            banco.apagar(p)


if __name__ == "__main__":
    main()
