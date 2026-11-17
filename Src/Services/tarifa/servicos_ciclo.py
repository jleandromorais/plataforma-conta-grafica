"""Situação do ciclo: onde o analista está no roteiro de 5 passos de um trimestre. SÓ LÊ.

Não existe conta nova aqui: o serviço junta o que já existe (a prévia da cascata, o SR proposto, a
SELIC do Banco Central, o VP e o SCG gravados) e traduz em "pronto, atenção, falta ou bloqueado".

Roteiro (trimestre civil T, ex.: Jul–Set/2026; o PR/PV de T é o trimestre do ciclo seguinte, ex.: Nov–Jan):
  1. pmpv_anterior  VP (PMPV) dos 3 meses de T gravado.
  2. pasta_scg      SCG dos 3 meses de T gravado (pasta processada).
  3. sr             SELIC de T fechada, SR calculado e gravado. NÃO exige o PMPV seguinte.
  4. pr_pv          exige SR gravado e o PMPV novo; PR e PV calculados e gravados.
  5. tarifa_media   só leitura: liberada quando o PV está gravado (a conta fica no PMPV).
"""
from __future__ import annotations

from datetime import date

from Src.common.formatting import format_brl
from Src.common.periodos import is_periodo_valido, normalizar_periodo
from Src.application.use_cases.sr_use_cases import vp_do_mes
from Src.infrastructure.repositories.sqlite_repositories import SqliteSRRepository
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
from Src.Services.tarifa import servicos_pr_automatico as auto
from Src.Services.tarifa import servicos_selic
from Src.Services.tarifa.servicos_cascata import TOL_SR, ServicosCascata, _chaves

PRONTO, ATENCAO, FALTA, BLOQUEADO = "pronto", "atencao", "falta", "bloqueado"


def meses_do_trimestre(trimestre: str) -> list[str]:
    """Aceita "Jul/2026_Set/2026" (o rótulo do SR) ou um mês qualquer do trimestre ("Ago/2026").
    Devolve os 3 meses civis. Trimestre que não existe → ValueError (422)."""
    texto = (trimestre or "").strip()
    primeiro = texto.split("_")[0]
    canonico = normalizar_periodo(primeiro)
    if not canonico or not is_periodo_valido(canonico):
        raise ValueError(f"O trimestre “{trimestre}” não é válido. Use o rótulo do SR, por exemplo "
                         "Jul/2026_Set/2026, ou um mês do trimestre, por exemplo Ago/2026.")
    meses = auto.meses_do_trimestre_civil(canonico)
    if "_" in texto and f"{meses[0]}_{meses[-1]}" != "_".join(normalizar_periodo(p) for p in texto.split("_")):
        raise ValueError(f"“{trimestre}” não é um trimestre civil (Jan–Mar, Abr–Jun, Jul–Set ou Out–Dez).")
    return meses


def _passo(numero: int, chave: str, titulo: str, estado: str, motivo: str, rota: str) -> dict:
    return {"passo": numero, "chave": chave, "titulo": titulo, "estado": estado, "motivo": motivo, "rota": rota}


class ServicosCiclo:
    def __init__(self, cascata: ServicosCascata | None = None):
        self._proprio = cascata is None
        self._cascata = cascata or ServicosCascata()

    def __enter__(self) -> "ServicosCiclo":
        return self

    def __exit__(self, *_exc) -> bool:
        self.fechar()
        return False

    def fechar(self) -> None:
        if self._proprio:
            self._cascata.fechar()

    # ── leituras do banco (sem conta) ───────────────────────────────────────

    @staticmethod
    def _meses_sem_vp(meses: list[str]) -> list[str]:
        repo = SqliteSRRepository()
        try:
            return [p for p in meses if not vp_do_mes(repo, p)]
        finally:
            repo.fechar()

    @staticmethod
    def _meses_sem_scg(meses: list[str]) -> list[str]:
        with ServicosConsolidacao() as cons:
            return [p for p in meses if not cons.buscar_consolidacao(p)]

    def _pmpv_novo(self, meses_pr: list[str]) -> dict:
        sem_vp = self._meses_sem_vp(meses_pr)
        tem_pmpv = bool(float(self._cascata._repo.buscar_pmpv_mensal(meses_pr[0]) or 0.0))
        return {"existe": not sem_vp and tem_pmpv, "meses": meses_pr, "meses_sem_vp": sem_vp,
                "tem_pmpv_mensal": tem_pmpv}

    # ── a situação ──────────────────────────────────────────────────────────

    def situacao(self, trimestre: str, hoje: date | None = None) -> dict:
        meses = meses_do_trimestre(trimestre)
        rotulo = f"{meses[0]}_{meses[-1]}"
        intervalo = f"{meses[0]} a {meses[-1]}"
        meses_pr = auto.meses_do_pr_do_civil(meses[0])
        chave_pr, chave_pv = _chaves(meses_pr)
        intervalo_pr = f"{meses_pr[0]} a {meses_pr[-1]}"

        selic = servicos_selic.fechamento_do_trimestre(meses, hoje, servicos_selic.buscar_bcb)
        pmpv_novo = self._pmpv_novo(meses_pr)

        # 1. PMPV do trimestre anterior (o VP dos meses de T)
        sem_vp = self._meses_sem_vp(meses)
        if sem_vp:
            p1 = _passo(1, "pmpv_anterior", "PMPV do trimestre anterior", FALTA,
                        f"Falta o VP de {', '.join(sem_vp)}: salve o PMPV que cobre esses meses.", "/pmpv")
        else:
            p1 = _passo(1, "pmpv_anterior", "PMPV do trimestre anterior", PRONTO,
                        f"VP de {intervalo} gravado.", "/pmpv")

        # 2. Processar a pasta (SCG dos 3 meses)
        sem_scg = self._meses_sem_scg(meses)
        if sem_scg:
            p2 = _passo(2, "pasta_scg", "Processar a pasta com SCG", FALTA,
                        f"Falta o SCG de {', '.join(sem_scg)}: processe a pasta do ciclo e salve.", "/ciclo")
        else:
            p2 = _passo(2, "pasta_scg", "Processar a pasta com SCG", PRONTO,
                        f"SCG de {intervalo} gravado.", "/ciclo")

        # 3. SR (não exige o PMPV seguinte)
        p3 = self._passo_sr(meses, intervalo, selic, p1, p2)

        # 4. PR e PV (exigem SR gravado e o PMPV novo)
        p4 = self._passo_pr_pv(meses[0], intervalo, intervalo_pr, p3, pmpv_novo)

        # 5. Tarifa média (só leitura)
        if p4["estado"] == PRONTO:
            p5 = _passo(5, "tarifa_media", "Tarifa média", PRONTO,
                        f"PV de {chave_pv} gravado: confira a tarifa média e feche no PMPV.", "/pmpv")
        else:
            p5 = _passo(5, "tarifa_media", "Tarifa média", BLOQUEADO,
                        f"Depende do PV de {chave_pv} gravado (passo 4).", "/pmpv")

        passos = [p1, p2, p3, p4, p5]
        proximo = next((p["chave"] for p in passos if p["estado"] != PRONTO), None)
        return {"trimestre": rotulo, "meses": meses,
                "trimestre_pr": {"meses": meses_pr, "chave_pr": chave_pr, "chave_pv": chave_pv},
                "selic": selic, "pmpv_novo": pmpv_novo, "passos": passos, "proximo_passo": proximo}

    def _passo_sr(self, meses: list[str], intervalo: str, selic: dict, p1: dict, p2: dict) -> dict:
        def passo(estado: str, motivo: str) -> dict:
            return _passo(3, "sr", "SR", estado, motivo, "/ciclo")

        if not selic["fechada"]:
            return passo(BLOQUEADO, selic["motivo"])
        antes = [p for p in (p1, p2) if p["estado"] != PRONTO]
        if antes:
            return passo(BLOQUEADO, f"Antes, conclua o passo {antes[0]['passo']}: {antes[0]['motivo']}")
        previa = self._cascata.previa([meses[0]], "sr", ate="sr")
        item = previa["trimestres"][0]
        if previa["pendencias"] or item["sr_novo"] is None:
            return passo(FALTA, " ".join(previa["pendencias"]) or f"Não foi possível calcular o SR de {intervalo}.")
        novo, gravado = item["sr_novo"], item["sr_antes"]
        if gravado is None:
            return passo(ATENCAO, f"SR de {intervalo} calculado ({format_brl(novo)}), ainda não gravado: "
                                  "confira e aprove.")
        if abs(novo - gravado) > TOL_SR:
            return passo(ATENCAO, f"O SR gravado ({format_brl(gravado)}) difere do recalculado "
                                  f"({format_brl(novo)}): confira e aprove.")
        return passo(PRONTO, f"SR de {intervalo} gravado ({format_brl(gravado)}).")

    def _passo_pr_pv(self, guia: str, intervalo: str, intervalo_pr: str, p3: dict, pmpv_novo: dict) -> dict:
        def passo(estado: str, motivo: str, rota: str = "/ciclo") -> dict:
            return _passo(4, "pr_pv", "PR e PV", estado, motivo, rota)

        if p3["estado"] != PRONTO:
            return passo(BLOQUEADO, f"Antes, grave o SR de {intervalo} (passo 3).")
        if not pmpv_novo["existe"]:
            faltam = (f"o VP de {', '.join(pmpv_novo['meses_sem_vp'])}" if pmpv_novo["meses_sem_vp"]
                      else f"o PMPV de {pmpv_novo['meses'][0]}")
            return passo(BLOQUEADO, f"Falta {faltam} ({intervalo_pr}): salve o PMPV do trimestre novo.", "/pmpv")
        previa = self._cascata.previa([guia], "pr")
        item = previa["trimestres"][0]
        if previa["pendencias"] or item["pr_novo"] is None or item["pv_novo"] is None:
            return passo(FALTA, " ".join(previa["pendencias"]) or f"Não foi possível calcular o PR e o PV de {intervalo_pr}.")
        if item["desatualizado"]:
            return passo(ATENCAO, f"PR e PV de {intervalo_pr} calculados, ainda não gravados ou diferentes do "
                                  "gravado: confira e aprove.")
        return passo(PRONTO, f"PR e PV de {intervalo_pr} gravados.")
