"""Perfis de acesso e "quem fez" na trilha (matriz da Amanda, docs/PERFIS.md).

Desligado por padrão: com PERFIS_ATIVOS=0 (ou ausente) todo usuário logado continua podendo tudo e esta
camada só ANOTA quem fez (nome, e-mail, perfis, ação) na trilha. Com PERFIS_ATIVOS=1 a matriz abaixo vale e
quem não tem o perfil recebe 403 com uma frase dizendo quem pode.

Como funciona: `controle_de_acesso` roda antes de toda rota protegida (Src/api/main.py), descobre a regra da
rota na tabela `REGRAS`, confere o perfil (lido do banco a cada requisição, em `auth.usuario_atual`) e
guarda quem está agindo para a trilha (`database.definir_ator_da_alteracao`).
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from Src.api.auth import PERFIS, perfis_ativos, usuario_atual
from Src.Database import database

# ── grupos de perfis (colunas da matriz) ───────────────────────────────────
LER = frozenset(PERFIS)                                              # ver telas, provas reais, trilha
GRAVAR_MODULO = frozenset({"operador", "analista", "administrador"})  # processar a pasta e gravar módulo
ESCOLHER = frozenset({"analista"})                                   # SCG gravado × soma, SR anterior, SELIC manual, MB
APROVAR = frozenset({"aprovador", "analista"})                       # aprovar SR, PR e PV
FECHAR = frozenset({"analista"})                                     # revisar e fechar o trimestre (rota ainda não existe)
APAGAR = frozenset({"administrador"})                                # apagar PR, período, SCG; limpar dados de teste
REPARAR = frozenset({"administrador"})                               # reparar histórico do SCG (analista é "condicional": fora)
RELATORIO_OFICIAL = frozenset({"analista", "administrador"})         # aprovador é "condicional": fora
ADMINISTRAR = frozenset({"administrador"})                           # usuários e perfis


@dataclass(frozen=True)
class Regra:
    acao: str                     # nome curto que vai para a trilha
    descricao: str                # frase usada na mensagem de recusa
    perfis: frozenset[str]        # quem pode
    sempre: bool = False          # True: vale mesmo com PERFIS_ATIVOS=0 (rotas novas de administração)


_LER = Regra("ver", "ver esta tela", LER)
_CALC = Regra("calcular", "fazer este cálculo", LER)                  # só calcula/mostra prévia: não grava
_GRAVAR = Regra("salvar_modulo", "processar a pasta e gravar o módulo", GRAVAR_MODULO)
_APROVAR_SR = Regra("aprovar_sr", "aprovar o SR", APROVAR)
_APROVAR_PR = Regra("aprovar_pr", "aprovar o PR", APROVAR)
_APROVAR_PV = Regra("aprovar_pv", "aprovar o PV", APROVAR)
_APROVAR_CASCATA = Regra("aprovar_cascata", "aprovar SR, PR e PV", APROVAR)
_RELATORIO = Regra("relatorio_oficial", "gerar o relatório oficial do trimestre", RELATORIO_OFICIAL)

# (método, caminho da rota como declarado) → regra. GET não precisa estar aqui (vale `_LER`).
REGRAS: dict[tuple[str, str], Regra] = {
    # Auditoria
    ("POST", "/api/auditoria/processar"): _GRAVAR,
    ("POST", "/api/auditoria/planilha/conferir"): _GRAVAR,
    ("POST", "/api/auditoria/salvar"): _GRAVAR,
    ("POST", "/api/auditoria/remover-nota"): _GRAVAR,
    ("POST", "/api/auditoria/incluir-nota"): _GRAVAR,
    ("POST", "/api/auditoria/diferencas"): _CALC,
    ("POST", "/api/auditoria/relatorio"): _CALC,
    # CGF, RET, Conciliação, RPV
    ("POST", "/api/cgf/processar"): _GRAVAR,
    ("POST", "/api/cgf/calcular-rs"): _CALC,
    ("POST", "/api/cgf/salvar"): _GRAVAR,
    ("POST", "/api/ret/processar"): _GRAVAR,
    ("POST", "/api/ret/salvar"): _GRAVAR,
    ("POST", "/api/ret/remover-documento"): _GRAVAR,
    ("POST", "/api/conciliacao/processar"): _GRAVAR,
    ("POST", "/api/conciliacao/salvar"): _GRAVAR,
    ("POST", "/api/conciliacao/remover-nota"): _GRAVAR,
    ("POST", "/api/conciliacao/relatorio"): _CALC,
    ("POST", "/api/rpv/salvar"): _GRAVAR,
    # SCG
    ("POST", "/api/scg/salvar"): _GRAVAR,          # com `escolha` vira "escolher" (ver escolha_com_motivo)
    ("POST", "/api/scg/manual"): _GRAVAR,
    ("POST", "/api/scg/calcular"): _GRAVAR,        # recalcula e GRAVA RPV e SCG do mês
    ("POST", "/api/scg/reparar-historico"): Regra("reparar_scg", "reparar o histórico do SCG", REPARAR),
    ("DELETE", "/api/scg"): Regra("apagar_scg", "apagar o SCG de um mês", APAGAR),
    # PMPV
    ("POST", "/api/pmpv/calcular"): _CALC,
    ("POST", "/api/pmpv/salvar"): _GRAVAR,
    ("POST", "/api/pmpv/mensal/{periodo:path}"): _GRAVAR,
    ("POST", "/api/pmpv/trimestre-ativo"): _GRAVAR,
    ("POST", "/api/pmpv/importar-memoria"): _GRAVAR,
    ("POST", "/api/pmpv/margem-regulatoria"): Regra("escolher_mb", "escolher a MB (margem de distribuição)", ESCOLHER),
    # SR, PR, PV, cascata
    ("POST", "/api/sr/calcular"): _CALC,
    ("POST", "/api/sr/trimestre/carregar"): _CALC,
    ("POST", "/api/sr/trimestre/proposta"): _CALC,
    ("POST", "/api/sr/trimestre/calcular"): _CALC,
    ("POST", "/api/sr/trimestre/salvar"): _APROVAR_SR,
    ("POST", "/api/pr/apurar"): _CALC,
    ("POST", "/api/pr/salvar"): _APROVAR_PR,
    ("DELETE", "/api/pr"): Regra("apagar_pr", "apagar o PR de um trimestre", APAGAR),
    ("POST", "/api/pv/periodos"): _GRAVAR,
    ("POST", "/api/pv/salvar"): _APROVAR_PV,
    ("POST", "/api/pv/trimestre/salvar"): _APROVAR_PV,
    ("POST", "/api/cascata/aplicar"): _APROVAR_CASCATA,
    # Arquivos gerados
    ("POST", "/api/excel-final/gerar"): _GRAVAR,
    ("POST", "/api/excel-final/gerar-geral"): _GRAVAR,
    ("POST", "/api/nota-tecnica/gerar"): _RELATORIO,
    ("POST", "/api/relatorio-trimestral/gerar"): _RELATORIO,
    # Limpeza e administração
    ("DELETE", "/api/periodos/{nome:path}"): Regra("apagar_periodo", "apagar um período de teste", APAGAR),
    ("GET", "/api/usuarios"): Regra("listar_usuarios", "ver os usuários e perfis", ADMINISTRAR, sempre=True),
    ("PUT", "/api/usuarios/{usuario_id}/perfis"): Regra("definir_perfis", "mudar perfis de usuários", ADMINISTRAR, sempre=True),
}


def regra_da_rota(metodo: str, caminho: str) -> Regra:
    """Regra da rota. Rota que ninguém classificou: GET é leitura; o resto exige gravar módulo (o teste
    `test_perfis.py` falha se uma rota nova ficar fora da tabela, então isto é só a rede de segurança)."""
    regra = REGRAS.get((metodo.upper(), caminho))
    if regra:
        return regra
    return _LER if metodo.upper() in ("GET", "HEAD", "OPTIONS") else _GRAVAR


def _recusa(usuario: dict, regra: Regra, quem_pode: frozenset[str]) -> HTTPException:
    meus = ", ".join(usuario.get("perfis") or []) or "nenhum"
    pode = ", ".join(p for p in PERFIS if p in quem_pode)
    return HTTPException(403, f"Seu perfil ({meus}) não permite {regra.descricao}. "
                              f"Quem pode: {pode}. Peça ao administrador para ajustar seu perfil.")


def verificar(usuario: dict, regra: Regra) -> str | None:
    """Confere o perfil. Devolve o perfil que deu acesso (ou, com PERFIS_ATIVOS=0, os perfis da pessoa,
    só para a trilha). Sem permissão → 403."""
    meus = [p for p in (usuario.get("perfis") or []) if p in PERFIS]
    if perfis_ativos() or regra.sempre:
        usados = [p for p in meus if p in regra.perfis]
        if not usados:
            raise _recusa(usuario, regra, regra.perfis)
        return usados[0]
    return ",".join(meus) or None


async def controle_de_acesso(request: Request, usuario: dict = Depends(usuario_atual)) -> None:
    """Roda antes de toda rota protegida: confere o perfil e anota quem está agindo para a trilha.

    É `async def` de propósito: só assim o "quem" fica visível para o código da rota (que o FastAPI roda
    numa thread) e chega até a gravação da trilha. Não faz leitura de banco aqui: o perfil já veio de
    `usuario_atual`."""
    rota = request.scope.get("route")
    caminho = getattr(rota, "path", request.url.path)
    # Conforme a versão do FastAPI, o caminho da rota vem com ou sem o prefixo "/api" do include_router.
    if not caminho.startswith("/api/"):
        caminho = "/api" + caminho
    regra = regra_da_rota(request.method, caminho)
    perfil = verificar(usuario, regra)
    database.definir_ator_da_alteracao({
        "id": usuario.get("id"), "nome": usuario.get("nome"), "email": usuario.get("email"),
        "perfil": perfil, "acao": regra.acao, "motivo": None, "perfis": list(usuario.get("perfis") or []),
    })


def exigir_perfil(*aceitos: str):
    """Dependência para travar UMA rota a certos perfis (além da matriz geral):
    `Depends(exigir_perfil("analista"))`. Com PERFIS_ATIVOS=0 deixa passar. Devolve o usuário."""
    desconhecidos = [p for p in aceitos if p not in PERFIS]
    if desconhecidos:
        raise ValueError(f"Perfil inexistente: {', '.join(desconhecidos)}.")
    regra = Regra("restrita", "fazer esta ação", frozenset(aceitos))

    def _dependencia(usuario: dict = Depends(usuario_atual)) -> dict:
        verificar(usuario, regra)
        return usuario

    return _dependencia


def escolha_com_motivo(motivo: str | None) -> str | None:
    """Para as ESCOLHAS do analista (SCG gravado × soma, SR anterior, SELIC manual, MB). Chame dentro da rota.

    Com PERFIS_ATIVOS=1: só o perfil analista, e o motivo é obrigatório (sem ele, 422). Com PERFIS_ATIVOS=0:
    não exige nada; só anota o motivo, se vier. Devolve o motivo já limpo."""
    texto = (motivo or "").strip() or None
    ator = database.ator_da_alteracao()
    if perfis_ativos():
        regra = Regra("escolher", "fazer esta escolha (SCG gravado ou soma, SR anterior, SELIC manual ou MB)", ESCOLHER)
        verificar({"perfis": (ator or {}).get("perfis") or []}, regra)
        if not texto:
            raise ValueError("Esta escolha precisa de um motivo: escreva por que você escolheu este valor "
                             "(ele fica registrado na trilha, com o seu nome).")
    if ator is not None:
        ator["acao"] = "escolher"
        ator["motivo"] = texto
        if perfis_ativos():
            ator["perfil"] = "analista"
    return texto


def anotar_motivo(motivo: str | None) -> None:
    """Guarda um motivo opcional (por exemplo, ao apagar) para a trilha. Não exige nada."""
    ator = database.ator_da_alteracao()
    texto = (motivo or "").strip() or None
    if ator is not None and texto:
        ator["motivo"] = texto
