"""Casos de uso do módulo SR trimestral (camada application).

Extraído de Src/Views/tela_sr.py (TelaSR._get_trimestre_labels,
_carregar_do_banco, _calcular, _salvar) — essa lógica hoje só existia dentro
da View, chamando DatabasePMPV diretamente. Ver SPEC_SR.md §4.

Fórmula por mês:
    diferenca  = VP - VF
    sr_parcela = diferenca * PR
    sr_selic   = sr_parcela * (1 + SELIC% / 100) + SR_anterior

SR TOTAL = soma de sr_selic de todos os meses do trimestre.
"""
from __future__ import annotations

import re
from typing import Any

from Src.common.periodos import (
    TRIMESTRES_FISCAIS_ABREVS, deslocar_periodo, is_periodo_valido, labels_meses, normalizar_periodo, periodo_sort_key,
)
from Src.common.precisao import arredondar_tarifa
from Src.domain.ports.repositories import SRRepository
from Src.infrastructure.repositories.sqlite_repositories import SqliteSRRepository
from Src.Services.tarifa import servicos_selic
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao


def labels_trimestre(meses: list[str], ano: int) -> list[str]:
    """Reproduz TelaSR._get_trimestre_labels: monta os labels 'Mes/Ano' do
    trimestre, avançando o ano na virada (ex.: Nov, Dez, Jan). A lógica fica
    em Src/common/periodos.labels_meses (também usada pelo PV)."""
    return labels_meses(meses, ano)


def _trimestre_label(labels: list[str]) -> str:
    return f"{labels[0]}_{labels[-1]}"


def meses_do_trimestre_label(trimestre: str) -> list[str]:
    """'Jan/2026_Mar/2026' → ['Jan/2026', 'Fev/2026', 'Mar/2026']. Texto que não seja
    "Mês/Ano_Mês/Ano" com 3 meses seguidos → ValueError (vira 422)."""
    erro = ValueError(f"O trimestre “{trimestre}” não é válido. Use o formato Jan/2026_Mar/2026 (3 meses seguidos).")
    partes = (trimestre or "").split("_")
    if len(partes) != 2:
        raise erro
    ini, fim = normalizar_periodo(partes[0]), normalizar_periodo(partes[1])
    if not (is_periodo_valido(ini) and is_periodo_valido(fim)):
        raise erro
    meses = [deslocar_periodo(ini, i) for i in range(3)]
    if meses[-1] != fim:
        raise erro
    return meses


# Tolerâncias da prova real do SR
TOL_CONTA_SR = 0.01                                                     # R$ por mês
TOL_FONTES = {"vp": 1.0, "vf": 1.0, "pr": 1e-4, "selic_mensal": 5e-7}  # volumes em m³


_RE_NOME_SESSAO =re.compile(r"^PMPV_([A-Za-z]{3})_+([A-Za-z]{3})_(\d{4})$")


def periodos_da_sessao(nome: str) -> list[str]:
    """Meses do calendário de uma sessão salva pelo PMPV ("PMPV_Fev___Abr_2026"
    → Fev/2026, Mar/2026, Abr/2026; "PMPV_Nov___Jan_2025" → Nov/2025 … Jan/2026).
    Nome em outro formato (ex.: "PMPV_13042026_0906") → []."""
    m = _RE_NOME_SESSAO.match(nome or "")
    if not m:
        return []
    inicio, fim, ano = m.group(1).capitalize(), m.group(2).capitalize(), int(m.group(3))
    for _, meses in TRIMESTRES_FISCAIS_ABREVS:
        if meses[0] == inicio and meses[-1] == fim:
            return [normalizar_periodo(p) for p in labels_trimestre(meses, ano)]
    return []


def vp_do_mes(repo: SRRepository, periodo: str) -> float:
    """VP (m³) de um mês do calendário, vindo do PMPV que cobre esse mês.

    1º a tabela vp_mensal (gravada ao salvar o PMPV); senão, a sessão mais
    recente cujo nome indica o trimestre que contém o mês. Nunca usa a posição
    (mês 1/2/3) de uma sessão de outro trimestre: era isso que deslocava o VP
    quando o SR (Jan–Mar) não coincidia com o trimestre do PMPV (Fev–Abr).
    Sem PMPV para o mês → 0.0.
    """
    vp = repo.buscar_vp_periodo(periodo)
    if vp is not None:
        return vp
    alvo = normalizar_periodo(periodo)
    for sessao in repo.listar_sessoes_id_nome():
        periodos = periodos_da_sessao(sessao.get("nome", ""))
        if alvo in periodos:
            dados_mes = repo.carregar_dados_mes(sessao["id"], periodos.index(alvo) + 1) or []
            return sum(float(l.get("volume", 0) or 0) for l in dados_mes)
    return 0.0


_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def chave_pr_do_mes(periodo: str) -> str:
    """Chave sob a qual a tela PR grava o PR do trimestre que contém o mês.

    Os PRs vão de Nov–Jan, Fev–Abr, Mai–Jul e Ago–Out; a chave é "Ago - Out/2026"
    (o ano é o do último mês do trimestre). Jul/2026 → "Mai - Jul/2026"."""
    mes, ano = normalizar_periodo(periodo).split("/")
    i = _ABREV.index(mes)
    inicio = i - ((i + 2) % 3)                       # mês de início do trimestre do PR (pode ser < 0: Nov/Dez do ano anterior)
    fim = inicio + 2
    return f"{_ABREV[inicio % 12]} - {_ABREV[fim % 12]}/{int(ano) + (fim // 12 - i // 12)}"


def _num(valor: float, casas: int) -> str:
    """Número no padrão brasileiro (vírgula decimal, ponto de milhar) para as mensagens."""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_br(iso: str) -> str:
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


class SRUseCases:
    def __init__(self, repo: SRRepository | None = None):
        self.repo = repo or SqliteSRRepository()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.fechar()
        return False

    def carregar_vp_vf_pr(self, sessao_id: int, labels_meses: list[str]) -> list[dict[str, Any]]:
        """Para cada mês do trimestre, preenche VP (do PMPV que cobre aquele mês
        do calendário — ver `vp_do_mes`), VF (volume_final do CGF do período) e
        PR. Regra do PR (aba SR da Nota Técnica): o SR do mês M usa o PR que estava
        na tarifa de M, o do trimestre fiscal (Nov–Jan, Fev–Abr, Mai–Jul, Ago–Out)
        que contém o próprio mês — a mesma chave em que a tela PR grava o PR
        aplicado nesse trimestre (Out → "Ago - Out"; Nov, Dez → "Nov - Jan"). 1º o PR salvo na tela PR para essa
        chave ("salvo"); 2º estimado por (SCG + SR) ÷ VP ("estimado"); senão "ausente".
        `pr_chave` diz a chave do PR usado ("" se não é "salvo").
        `sessao_id` fica na assinatura por compatibilidade; o VP não depende dela."""
        resultado = []
        servicos_cons = ServicosConsolidacao()
        try:
            for periodo in labels_meses:
                vp = vp_do_mes(self.repo, periodo)

                resumo = self.repo.buscar_cgf_resumo(periodo)
                vf = float(resumo["volume_final"]) if resumo and resumo.get("volume_final") is not None else 0.0

                chave = chave_pr_do_mes(periodo)
                pr_tela = self.repo.buscar_pr(chave)
                pr = float((pr_tela or {}).get("pr") or 0.0)
                pr_origem = "salvo" if pr else "ausente"
                pr_chave = chave if pr else ""
                if pr == 0.0 and vp > 0:
                    pr_row = self.repo.buscar_sr(periodo)
                    dados_cons = servicos_cons.buscar_consolidacao(periodo)
                    scg_m = float((dados_cons or {}).get("scg") or 0.0)
                    sr_m = float((pr_row or {}).get("sr") or 0.0)
                    pr = (scg_m + sr_m) / vp if vp else 0.0
                    pr_origem = "estimado" if pr else "ausente"

                resultado.append({"mes": periodo, "vp": vp, "vf": vf, "pr": pr,
                                  "pr_origem": pr_origem, "pr_chave": pr_chave})
        finally:
            servicos_cons.fechar()
        return resultado

    def propor_trimestre(self, labels_meses: list[str], buscar=None) -> dict[str, Any]:
        """Proposta do SR do trimestre: calcula VP, VF, PR e SELIC sozinho, compara
        com o que está gravado e diz o que impede de gravar. SÓ LÊ: não grava nada."""
        buscar = buscar or servicos_selic.buscar_bcb
        base = self.carregar_vp_vf_pr(0, labels_meses)

        # SELIC do Banco Central (trimestre aberto ou BC fora do ar → 0, com aviso).
        selic = {"disponivel": False, "fecha_em": "", "fonte": "Banco Central (série 11)", "mensagem": ""}
        valores: dict[str, float] = {}
        try:
            r = servicos_selic.selic_do_trimestre(labels_meses, buscar=buscar)
            selic.update(disponivel=r["disponivel"], fecha_em=r["fecha_em"], fonte=r["fonte"])
            valores = r["valores"] if r["disponivel"] else {}
            if not r["disponivel"]:
                selic["mensagem"] = f"O trimestre só fecha em {_data_br(r['fecha_em'])}; a SELIC ainda não está disponível."
        except (servicos_selic.SelicIndisponivel, ValueError) as exc:  # BC fora do ar ou meses que não formam um trimestre
            selic["mensagem"] = str(exc)
        if not selic["fecha_em"]:
            try:
                selic["fecha_em"] = servicos_selic.fim_do_trimestre(labels_meses).isoformat()
            except ValueError:
                pass

        gravados = {g["mes"]: g for g in self.buscar_trimestre(labels_meses)}
        entradas = []
        for b in base:
            g = gravados.get(b["mes"])
            entradas.append({
                "mes": b["mes"], "vp": b["vp"], "vf": b["vf"], "pr": arredondar_tarifa(b["pr"]),
                "selic_mensal": float(valores.get(b["mes"], 0.0)),
                "sr_anterior": float((g or {}).get("sr_anterior") or 0.0),
            })
        calculo = self.calcular_trimestre(entradas)

        bloqueios: list[str] = []
        linhas = []
        for b, c in zip(base, calculo["linhas"]):
            mes = b["mes"]
            g = gravados.get(mes)
            gravado = None
            if g:
                gravado = {k: float(g.get(k) or 0.0) for k in ("vp", "vf", "pr", "selic_mensal", "sr_selic", "sr_anterior")}
            alertas: list[dict[str, str]] = []

            if c["vp"] == 0:
                msg = f"Sem VP de {mes}: salve o PMPV do trimestre que contém {mes} na tela PMPV."
                alertas.append({"codigo": "sem_vp", "mensagem": msg})
                bloqueios.append(msg)
            tri_pr = chave_pr_do_mes(mes).replace(" - ", "–")
            if b["pr_origem"] == "ausente":
                msg = f"Não há PR salvo para {mes} (trimestre {tri_pr}): rode a tela PR."
                alertas.append({"codigo": "pr_ausente", "mensagem": msg})
                bloqueios.append(msg)
            elif b["pr_origem"] == "estimado":
                # Estimativa (SCG + SR) ÷ VP é circular e já deu SR muito errado: não se grava em cima dela.
                msg = (f"O PR de {mes} é só uma estimativa (não há PR salvo para o trimestre {tri_pr}): "
                       "rode a tela PR desse trimestre antes de gravar o SR.")
                alertas.append({"codigo": "pr_estimado", "mensagem": msg})
                bloqueios.append(msg)
            if c["vf"] == 0:
                msg = f"Sem CGF gravado em {mes} (volume final): processe o CGF."
                alertas.append({"codigo": "vf_ausente", "mensagem": msg})
                bloqueios.append(msg)
            if not selic["disponivel"]:
                msg = selic["mensagem"] or "A SELIC não está disponível; ficaria 0%."
                alertas.append({"codigo": "selic_indisponivel", "mensagem": msg})
                if msg not in bloqueios:   # a mesma frase vale para os 3 meses: aparece uma vez
                    bloqueios.append(msg)
            elif gravado and gravado["selic_mensal"] == 0 and c["selic_mensal"] > 0:
                alertas.append({"codigo": "selic_zero_gravada",
                                "mensagem": f"O SR gravado está com SELIC 0%; o BC dá {_num(c['selic_mensal'], 6)}%."})
            if gravado:
                difs = []
                comparar = [("vp", 1.0, 0), ("vf", 1.0, 0), ("pr", 1e-4, 4)]
                if selic["disponivel"]:  # sem SELIC, comparar SELIC e SR só geraria falso alarme
                    comparar += [("selic_mensal", 5e-7, 6), ("sr_selic", 0.01, 2)]
                for campo, tol, casas in comparar:
                    if abs(c[campo] - gravado[campo]) > tol:
                        difs.append(f"{campo} (gravado {_num(gravado[campo], casas)} × novo {_num(c[campo], casas)})")
                if difs:
                    alertas.append({"codigo": "difere_gravado",
                                    "mensagem": f"Difere do gravado em {mes}: " + "; ".join(difs) + "."})

            linhas.append({**c, "pr_origem": b["pr_origem"], "pr_chave": b["pr_chave"],
                           "gravado": gravado, "alertas": alertas})

        total_gravado = sum(float(x.get("sr_selic") or 0.0) for x in gravados.values()) if gravados else None
        return {
            "labels_meses": labels_meses,
            "linhas": linhas,
            "total": calculo["total"],
            "total_gravado": total_gravado,
            "diferenca_total": None if total_gravado is None else calculo["total"] - total_gravado,
            "selic": selic,
            "bloqueios": bloqueios,
            "pode_gravar": not bloqueios,
        }

    @staticmethod
    def calcular_trimestre(linhas: list[dict[str, Any]]) -> dict[str, Any]:
        """Aplica a fórmula linha a linha. `linhas` é uma lista de
        {mes, vp, vf, pr, selic_mensal, sr_anterior}."""
        calculadas = []
        total = 0.0
        for linha in linhas:
            vp = float(linha.get("vp") or 0)
            vf = float(linha.get("vf") or 0)
            pr = float(linha.get("pr") or 0)
            selic = float(linha.get("selic_mensal") or 0)
            sr_anterior = float(linha.get("sr_anterior") or 0)

            diferenca = vp - vf
            sr_parcela = diferenca * pr
            sr_selic = sr_parcela * (1 + selic / 100) + sr_anterior

            calculadas.append({
                "mes": linha["mes"],
                "vp": vp,
                "vf": vf,
                "pr": pr,
                "selic_mensal": selic,
                "diferenca": diferenca,
                "sr_parcela": sr_parcela,
                "sr_selic": sr_selic,
                "sr_anterior": sr_anterior,
                "total": sr_selic,
            })
            total += sr_selic

        return {"linhas": calculadas, "total": total}

    def salvar_trimestre(
        self,
        labels_meses: list[str],
        periodo_referencia: str,
        linhas_calculadas: list[dict[str, Any]],
    ) -> float:
        """Persiste o trimestre: total em sr_resultados(periodo_referencia),
        cada mês em sr_resultados(periodo_mes), e todas as linhas em
        sr_trimestre. Retorna o total salvo."""
        total = sum(r["sr_selic"] for r in linhas_calculadas)
        vp_tot = sum(r["vp"] for r in linhas_calculadas)
        vf_tot = sum(r["vf"] for r in linhas_calculadas)

        self.repo.salvar_sr(periodo_referencia, vp_tot, vf_tot, 0.0, total)
        for i, r in enumerate(linhas_calculadas):
            periodo_mes = labels_meses[i] if i < len(labels_meses) else r["mes"]
            self.repo.salvar_sr(periodo_mes, r["vp"], r["vf"], r["pr"], r["sr_selic"])

        self.repo.salvar_sr_trimestre(_trimestre_label(labels_meses), linhas_calculadas)
        return total

    def buscar_trimestre(self, labels_meses: list[str]) -> list[dict[str, Any]]:
        return self.repo.buscar_sr_trimestre(_trimestre_label(labels_meses))

    def historico_trimestres(self) -> list[dict[str, Any]]:
        """Trimestres de SR gravados, do mais recente ao mais antigo."""
        linhas = []
        for tri in self.repo.listar_sr_trimestres():
            rows = self.repo.buscar_sr_trimestre(tri)
            if not rows:
                continue
            try:
                labels = meses_do_trimestre_label(tri)
            except ValueError:  # rótulo antigo fora do padrão: lista os meses gravados
                labels = [r["mes"] for r in rows]
            linhas.append({
                "trimestre": tri,
                "labels_meses": labels,
                "total": sum(float(r.get("sr_selic") or 0.0) for r in rows),
                "qtd_meses": len(rows),
                "data_atualizacao": max((r.get("data_atualizacao") or "" for r in rows), default="")[:16],
            })
        return sorted(linhas, key=lambda x: periodo_sort_key(x["trimestre"].split("_")[0]), reverse=True)

    def prova_real(self, trimestre: str, buscar=None) -> dict[str, Any]:
        """A conta do SR gravado do trimestre, refeita mês a mês com a MESMA `calcular_trimestre`
        do salvar, e o que as fontes (PMPV, CGF, PR, SELIC do BC) dizem HOJE (`propor_trimestre`).
        NÃO grava nada. SELIC fora do ar não derruba: `selic_mensal` das fontes vira None."""
        labels = meses_do_trimestre_label(trimestre)
        trimestre = _trimestre_label(labels)
        por_mes = {normalizar_periodo(r["mes"]): r for r in self.repo.buscar_sr_trimestre(trimestre)}
        gravadas = [por_mes[m] for m in labels if m in por_mes]
        if not gravadas:
            return {"trimestre": trimestre, "labels_meses": labels, "gravado": False, "linhas": [],
                    "total_gravado": 0.0, "total_recalculado": 0.0, "conta_confere": False,
                    "fontes_disponiveis": False,
                    "alertas": [{"codigo": "sem_sr_gravado",
                                 "mensagem": f"Ainda não há SR salvo para {labels[0]} a {labels[-1]}. Salve o SR deste trimestre na tela SR."}],
                    "data_atualizacao": ""}

        calculo = self.calcular_trimestre([
            {k: g.get(k) for k in ("mes", "vp", "vf", "pr", "selic_mensal", "sr_anterior")} for g in gravadas])

        proposta, alertas = None, []
        try:
            proposta = self.propor_trimestre(labels, buscar=buscar or servicos_selic.buscar_bcb)
        except (servicos_selic.SelicIndisponivel, ValueError) as exc:
            alertas.append({"codigo": "fontes_indisponiveis", "mensagem": str(exc)})
        selic_ok = bool(proposta and proposta["selic"]["disponivel"])
        propostas = {normalizar_periodo(l["mes"]): l for l in (proposta or {}).get("linhas", [])}

        linhas = []
        for g, c in zip(gravadas, calculo["linhas"]):
            gravado_sr = float(g.get("sr_selic") or 0.0)
            p = propostas.get(normalizar_periodo(g["mes"]))
            fontes = None
            if p:
                fontes = {"vp": p["vp"], "vf": p["vf"], "pr": p["pr"],
                          "selic_mensal": p["selic_mensal"] if selic_ok else None, "diferem": []}
                for campo, tol in TOL_FONTES.items():
                    if campo == "selic_mensal" and not selic_ok:
                        continue  # sem a SELIC do BC não há o que comparar
                    if abs(float(fontes[campo]) - float(g.get(campo) or 0.0)) > tol:
                        fontes["diferem"].append(campo)
            linhas.append({
                "mes": g["mes"], "vp": c["vp"], "vf": c["vf"], "pr": c["pr"], "selic_mensal": c["selic_mensal"],
                "sr_anterior": c["sr_anterior"], "diferenca": c["diferenca"], "sr_parcela": c["sr_parcela"],
                "sr_selic_recalculado": c["sr_selic"], "sr_selic_gravado": gravado_sr,
                "conta_confere": abs(c["sr_selic"] - gravado_sr) <= TOL_CONTA_SR,
                "fontes": fontes,
            })

        for l in (proposta or {}).get("linhas", []):  # repassa os avisos da proposta, sem repetir
            for a in l["alertas"]:
                if a not in alertas:
                    alertas.append(a)
        total_gravado = sum(l["sr_selic_gravado"] for l in linhas)
        total_recalculado = calculo["total"]
        return {
            "trimestre": trimestre, "labels_meses": labels, "gravado": True, "linhas": linhas,
            "total_gravado": total_gravado, "total_recalculado": total_recalculado,
            "conta_confere": all(l["conta_confere"] for l in linhas)
                             and abs(total_recalculado - total_gravado) <= TOL_CONTA_SR * len(linhas),
            "fontes_disponiveis": proposta is not None,
            "alertas": alertas,
            "data_atualizacao": max((g.get("data_atualizacao") or "" for g in gravadas), default="")[:16],
        }
