"""Dependency injection da API — uma instância de Service/Use Case por
request, cada uma abrindo sua própria conexão SQLite (via DatabasePMPV
default de cada repositório) e fechando ao final.
"""
from __future__ import annotations

from typing import Iterator

from Src.application.use_cases.pmpv_use_cases import PMPVUseCases
from Src.application.use_cases.sr_use_cases import SRUseCases
from Src.Services.servicos_scg import ServicosSCG
from Src.Services.servicos_pr import ServicosPR
from Src.Services.servicos_pv import ServicosPV
from Src.Services.servicos_rpv import ServicosRPV
from Src.Services.servicos_sr import ServicosSR
from Src.Services.servicos_consolidacao import ServicosConsolidacao


def get_pmpv_use_cases() -> Iterator[PMPVUseCases]:
    with PMPVUseCases() as uc:
        yield uc


def get_servicos_scg() -> Iterator[ServicosSCG]:
    servico = ServicosSCG()
    try:
        yield servico
    finally:
        servico.consolidacao.fechar()


def get_servicos_pr() -> Iterator[ServicosPR]:
    servico = ServicosPR()
    try:
        yield servico
    finally:
        servico._repo.fechar()


def get_servicos_pv() -> Iterator[ServicosPV]:
    servico = ServicosPV()
    try:
        yield servico
    finally:
        servico._repo.fechar()


def get_servicos_rpv() -> Iterator[ServicosRPV]:
    servico = ServicosRPV()
    try:
        yield servico
    finally:
        servico.consolidacao.fechar()


def get_servicos_sr() -> Iterator[ServicosSR]:
    servico = ServicosSR()
    try:
        yield servico
    finally:
        servico._repo.fechar()


def get_servicos_consolidacao() -> Iterator[ServicosConsolidacao]:
    with ServicosConsolidacao() as servico:
        yield servico


def get_sr_use_cases() -> Iterator[SRUseCases]:
    with SRUseCases() as uc:
        yield uc
