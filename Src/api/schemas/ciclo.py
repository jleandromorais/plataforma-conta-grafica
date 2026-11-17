"""Formato da situação do ciclo (GET /ciclo/situacao). Só leitura."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

EstadoPasso = Literal["pronto", "atencao", "falta", "bloqueado"]
EstadoSelic = Literal["aberta", "aguardando_publicacao", "indisponivel", "fechada"]


class CicloPasso(BaseModel):
    passo: int                    # 1 a 5
    chave: str                    # pmpv_anterior | pasta_scg | sr | pr_pv | tarifa_media
    titulo: str
    estado: EstadoPasso
    motivo: str                   # frase para o analista
    rota: str                     # rota do site para o link: "/pmpv", "/ciclo"...


class CicloSelic(BaseModel):
    fechada: bool
    estado: EstadoSelic
    fecha_em: str                 # AAAA-MM-DD: último dia do trimestre
    ultimo_dia_util: str          # AAAA-MM-DD (só fim de semana; feriado não entra)
    libera_em: str                # AAAA-MM-DD: ESTIMATIVA da liberação (1º dia útil depois do fim)
    publicada_ate: str | None = None   # última data da série do Banco Central (None se não consultou)
    motivo: str = ""


class CicloPmpvNovo(BaseModel):
    existe: bool                  # VP dos 3 meses e PMPV do 1º mês gravados
    meses: list[str]
    meses_sem_vp: list[str] = []
    tem_pmpv_mensal: bool = False


class CicloTrimestrePR(BaseModel):
    meses: list[str]
    chave_pr: str
    chave_pv: str


class CicloSituacao(BaseModel):
    trimestre: str                # "Jul/2026_Set/2026"
    meses: list[str]
    trimestre_pr: CicloTrimestrePR
    selic: CicloSelic
    pmpv_novo: CicloPmpvNovo
    passos: list[CicloPasso]
    proximo_passo: str | None = None   # chave do 1º passo que não está pronto; None = tudo pronto
