"""
pipeline.py — Motor de automação do GraphAccount Pro

Substitui o trabalho manual de 9 cliques no app desktop por um único
script que roda sozinho, agendado pelo Windows Task Scheduler (custo R$ 0).

Fluxo:
    1-4. Auditoria XML, RET, CGF e Conciliação — independentes entre si.
         Se uma falhar, as outras continuam (ex.: 1 PDF corrompido no RET
         não impede o processamento do CGF). As falhas são acumuladas.
    5. PMPV           (Preço Médio Ponderado de Venda)
    6. Consolidação   (SCG = RPV + RET + RP) — só roda se 1-5 OK; caso
       contrário o pipeline para aqui (SCG ficaria incompleto/errado) e
       envia um único e-mail listando TODAS as etapas que falharam.
    7. Excel Final    (relatório consolidado)
    8. Notificação    (e-mail de sucesso ou falha)

Uso:
    python pipeline.py
    python pipeline.py --periodo Mai/2026
    python pipeline.py --periodo Mai/2026 --pasta C:\\dados\\SCG-2026
    python pipeline.py --dry-run          (só valida pastas/arquivos, não processa)

O app desktop continua funcionando normalmente — serve de emergência quando
este script falhar ou quando precisar corrigir um número manualmente.
"""

from __future__ import annotations

import argparse
import logging
import sys
import os
import unicodedata
from datetime import datetime
from pathlib import Path

# Garante que o módulo Src seja encontrado mesmo rodando da raiz
sys.path.insert(0, str(Path(__file__).parent))

from Src.config.logging_config import configurar_logging

logger = logging.getLogger(__name__)

# ── Meses em PT-BR (mesmo padrão do app) ─────────────────────────────────────
_MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _num_br(valor: float, casas: int = 2) -> str:
    """Formata número no padrão BR (milhar '.', decimal ','), ex: 1.234.567,89.

    Usado nos logs/e-mails — o `%`-style do `logging` não aceita o separador
    de milhar `,` do f-string US diretamente (lança ValueError), e o público
    final (analista BR) espera o separador decimal local.
    """
    return f"{(valor or 0):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Helpers de período ────────────────────────────────────────────────────────

def _periodo_atual() -> str:
    """Retorna o período do mês atual: ex. 'Mai/2026'."""
    now = datetime.now()
    return f"{_MESES_ABREV[now.month - 1]}/{now.year}"


def _trimestre_atual(periodo: str) -> list[str]:
    """
    Dado um período (ex: 'Mai/2026'), retorna os 3 meses do trimestre.
    Trimestres regulatórios: Nov-Jan / Fev-Abr / Mai-Jul / Ago-Out.
    """
    mes_abrev, ano_str = periodo.split("/")
    ano = int(ano_str)
    mes_idx = _MESES_ABREV.index(mes_abrev)

    trimestres = [
        [10, 11, 0],   # Nov-Jan
        [1,  2,  3],   # Fev-Abr
        [4,  5,  6],   # Mai-Jul
        [7,  8,  9],   # Ago-Out
    ]

    grupo = next((t for t in trimestres if mes_idx in t), [mes_idx])

    resultado = []
    for idx in grupo:
        ano_mes = ano
        if grupo == [10, 11, 0]:
            # Trimestre Nov-Jan atravessa a virada de ano.
            # O ano de referência do trimestre é o do Jan (mês final).
            # Nov e Dez pertencem ao ano anterior ao Jan.
            # - Se o período informado é Jan (mes_idx=0): Nov/Dez → ano-1, Jan → ano
            # - Se o período informado é Nov ou Dez (mes_idx=10 ou 11): Nov/Dez → ano, Jan → ano+1
            if mes_idx == 0:
                # período = Jan/AAAA — Nov e Dez são do ano anterior
                if idx != 0:
                    ano_mes -= 1
            else:
                # período = Nov/AAAA ou Dez/AAAA — Jan é do ano seguinte
                if idx == 0:
                    ano_mes += 1
        resultado.append(f"{_MESES_ABREV[idx]}/{ano_mes}")

    return resultado


def _carregar_config() -> dict:
    """
    Lê configurações do config.env (se existir) e variáveis de ambiente.
    Variáveis de ambiente sobrescrevem o config.env.
    """
    config: dict[str, str] = {}

    config_path = Path(__file__).parent / "config.env"
    if config_path.exists():
        for linha in config_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            config[chave.strip()] = valor.strip()

    # Variáveis de ambiente têm prioridade — incluindo chaves novas não presentes no config.env
    _CHAVES_SUPORTADAS = {
        "PASTA_ENTRADA", "EMPRESA_PADRAO", "PMPV_VALOR_CG", "PMPV_ARQUIVO",
        "PMPV_ARQUIVO_NOV_JAN", "PMPV_ARQUIVO_FEV_ABR",
        "PMPV_ARQUIVO_MAI_JUL", "PMPV_ARQUIVO_AGO_OUT",
        "SUBPASTA_CGR", "SUBPASTA_RET", "SUBPASTA_CGF", "SUBPASTA_RP", "SUBPASTA_PMPV",
        "CGF_COL_VOLUME_FAT", "CGF_COL_CONSUMO", "CGF_VAL_CONSUMO",
        "CGF_COL_CANCELADAS", "CGF_COL_DEVOLUCOES",
        "EMAIL_REMETENTE", "EMAIL_SENHA_APP", "EMAIL_DESTINATARIO",
        "EMAIL_SMTP_HOST", "EMAIL_SMTP_PORT",
    }
    for chave in _CHAVES_SUPORTADAS | set(config.keys()):
        if chave in os.environ:
            config[chave] = os.environ[chave]

    return config


# ── Etapas do pipeline ────────────────────────────────────────────────────────

def _competencia_bate(caminho: Path, periodo: str) -> bool:
    """Verifica se o mês/ano extraído do caminho da subpasta bate com `periodo`.

    As pastas de entrada costumam agrupar vários meses (ex: `RET-jan-mar-26`
    contém `EAT jan26`, `EAT fev26`, `EAT mar26`; `CGR` tem uma subpasta por
    mês). Sem esse filtro, `rglob()` somaria documentos de competências
    diferentes num único total, distorcendo o fechamento do período pedido.
    """
    from Src.Services.servicos_ret import _extrair_mes_caminho

    mes_num, ano = _extrair_mes_caminho(str(caminho))
    if not mes_num:
        return True  # não foi possível identificar — não descarta o item
    return f"{_MESES_ABREV[mes_num - 1]}/{ano}" == periodo


def _etapa_auditoria(periodo: str, pasta: Path, cfg: dict) -> dict:
    """Lê XMLs de NF-e/CT-e, calcula CGR líquido e salva no banco."""
    from Src.Services.servicos_auditoria import RegrasAuditoria
    from Src.Database.database import DatabasePMPV

    empresa = cfg.get("EMPRESA_PADRAO", "COPERGÁS")

    if not pasta.exists():
        logger.warning("[Auditoria] Pasta não encontrada: %s — pulando etapa", pasta)
        return {"periodo": periodo, "cgr": 0.0, "n_itens": 0}

    xmls = [x for x in pasta.rglob("*.xml") if _competencia_bate(x, periodo)]
    logger.info("[Auditoria] %d XMLs em %s (competência %s)", len(xmls), pasta, periodo)

    itens = []
    for caminho in xmls:
        try:
            tipo = RegrasAuditoria.detectar_tipo_xml(caminho)
            if tipo == "nfe":
                dados = RegrasAuditoria.parse_nfe(caminho)
            elif tipo == "cte":
                dados = RegrasAuditoria.parse_cte(caminho)
            else:
                continue
            if dados and "erro" not in dados:
                dados["empresa"] = empresa
                valor_total = dados.get("valor_total", 0)
                icms_taxa = dados.get("icms_taxa", 0.0)
                dados["cgr_liquido"] = RegrasAuditoria.calcular_cgr_liquido(
                    valor_total,
                    valor_total * icms_taxa,
                )
                itens.append(dados)
        except Exception:
            logger.warning("[Auditoria] Falha ao processar %s", caminho.name, exc_info=True)

    cgr_total = sum(i.get("cgr_liquido", 0) for i in itens)
    logger.info("[Auditoria] %d documentos | CGR = R$ %s", len(itens), _num_br(cgr_total))

    with DatabasePMPV() as db:
        db.salvar_auditoria_itens(periodo, itens)
        db.atualizar_cgr(periodo, cgr_total)

    return {"periodo": periodo, "cgr": cgr_total, "n_itens": len(itens)}


def _etapa_ret(periodo: str, pasta: Path, cfg: dict) -> dict:
    """Lê PDFs de encargos (EAT/EC), calcula RET e salva no banco."""
    from Src.Services.servicos_ret import RegrasRET
    from Src.Database.database import DatabasePMPV

    if not pasta.exists():
        logger.warning("[RET] Pasta não encontrada: %s — pulando etapa", pasta)
        return {"periodo": periodo, "ret": 0.0, "n_itens": 0}

    pdfs_raw = [p for p in pasta.rglob("*.pdf") if _competencia_bate(p, periodo)]
    pdfs = [p for p in pdfs_raw if "substitui" not in _sem_acento(str(p)).lower()]
    if len(pdfs) != len(pdfs_raw):
        logger.info("[RET] %d PDFs excluídos por estar em pasta 'substituídas'", len(pdfs_raw) - len(pdfs))
    logger.info("[RET] %d PDFs em %s (competência %s)", len(pdfs), pasta, periodo)

    itens = []
    for caminho in pdfs:
        try:
            dados = RegrasRET.extrair_dados_pdf(str(caminho))
            if dados:
                itens.append(dados)
        except Exception:
            logger.warning("[RET] Falha ao processar %s", caminho.name, exc_info=True)

    resultado = RegrasRET.calcular_ret(itens) if itens else {"ret": 0.0}
    ret_total = float(resultado.get("ret", 0))
    logger.info("[RET] %d itens | RET = R$ %s", len(itens), _num_br(ret_total))

    with DatabasePMPV() as db:
        db.salvar_ret_itens(periodo, itens)
        db.atualizar_ret(periodo, ret_total)

    return {"periodo": periodo, "ret": ret_total, "n_itens": len(itens)}


def _etapa_cgf(periodo: str, pasta: Path, cfg: dict) -> dict:
    """Lê Excels de volume faturado/cancelado/devoluções, calcula VF e salva."""
    from Src.Services.servicos_cgf import ServicosCGF
    from Src.Database.database import DatabasePMPV

    if not pasta.exists():
        logger.warning("[CGF] Pasta não encontrada: %s — pulando etapa", pasta)
        return {"periodo": periodo, "volume_final": 0.0}

    excels = [e for e in pasta.rglob("*.xlsx") if _competencia_bate(e, periodo)]
    logger.info("[CGF] %d arquivos Excel em %s (competência %s)", len(excels), pasta, periodo)

    # Separa faturadas / canceladas / devoluções pelo nome do arquivo
    fat, canc, dev = [], [], []
    for c in excels:
        nome = c.stem.upper()
        if any(p in nome for p in ("CANCEL", "DENEGAD")):
            canc.append(c)
        elif "DEVOL" in nome:
            dev.append(c)
        else:
            fat.append(c)

    servico = ServicosCGF()
    resultado = servico.processar_arquivos(
        arquivos=fat + canc + dev,
        fat_col=cfg.get("CGF_COL_VOLUME_FAT", "Volume Faturado"),
        fat_cons_col=cfg.get("CGF_COL_CONSUMO", "Produto"),
        fat_cons_val=cfg.get("CGF_VAL_CONSUMO", "consumo proprio"),
        canc_col=cfg.get("CGF_COL_CANCELADAS", "Volume Canc/Deneg"),
        dev_col=cfg.get("CGF_COL_DEVOLUCOES", "Volume Devolução"),
    )

    vol_fat   = resultado.get("volume_faturado", 0)
    vol_canc  = resultado.get("volume_canceladas", 0)
    vol_dev   = resultado.get("volume_devolucoes", 0)
    vol_prop  = resultado.get("volume_consumo_proprio", 0)
    vol_final = resultado.get("volume_final", 0)

    logger.info(
        "[CGF] VF = %s m³ (fat=%s canc=%s dev=%s prop=%s)",
        _num_br(vol_final, 4), _num_br(vol_fat, 4), _num_br(vol_canc, 4), _num_br(vol_dev, 4), _num_br(vol_prop, 4),
    )

    with DatabasePMPV() as db:
        db.salvar_cgf_resumo(periodo, vol_fat, vol_canc, vol_dev, vol_prop, vol_final)
        db.atualizar_cgf(periodo, vol_final)

    return {"periodo": periodo, "volume_final": vol_final}


def _etapa_concilia(periodo: str, pasta: Path, cfg: dict) -> dict:
    """Lê PDFs de penalidades (Receita/Despesa), calcula RP e salva."""
    from Src.Services.servicos_concilia import RegrasConcilia
    from Src.Database.database import DatabasePMPV

    if not pasta.exists():
        logger.warning("[Conciliação] Pasta não encontrada: %s — pulando etapa", pasta)
        return {"periodo": periodo, "rp": 0.0, "n_itens": 0}

    pdfs_raw = [p for p in pasta.rglob("*.pdf") if _competencia_bate(p, periodo)]
    # Exclui versões substituídas/antigas (subpastas "substituídas" ou "Substituídos")
    pdfs = [p for p in pdfs_raw if "substitui" not in _sem_acento(str(p)).lower()]
    if len(pdfs) != len(pdfs_raw):
        logger.info("[Conciliação] %d PDFs excluídos por estar em pasta 'substituídas'", len(pdfs_raw) - len(pdfs))
    logger.info("[Conciliação] %d PDFs em %s (competência %s)", len(pdfs), pasta, periodo)

    # Separa Receita/Despesa pela estrutura de pastas
    pdfs_rec  = [p for p in pdfs if "RECEITA" in str(p).upper()]
    pdfs_desp = [p for p in pdfs if "DESPESA" in str(p).upper()]
    # Fallback: pastas não nomeadas — trata tudo como despesa
    if not pdfs_rec and not pdfs_desp:
        pdfs_desp = pdfs

    itens_rec  = RegrasConcilia.processar_arquivos(pdfs_rec,  "Receita",  lambda m: logger.info("[RP] %s", m)) if pdfs_rec  else []
    itens_desp = RegrasConcilia.processar_arquivos(pdfs_desp, "Despesa",  lambda m: logger.info("[RP] %s", m)) if pdfs_desp else []

    def _para_dict(item) -> dict:
        """Normaliza PdfItem (dataclass, campo `amount`) e dict para um formato
        único — o restante do pipeline e o DatabasePMPV esperam dicts com `valor`."""
        if isinstance(item, dict):
            return {
                "arquivo": item.get("arquivo", item.get("file_name", "")),
                "categoria": item.get("categoria", item.get("category", "")),
                "valor": float(item.get("valor", item.get("amount", 0)) or 0),
                "status": item.get("status", ""),
                "metodo": item.get("metodo", item.get("method", "")),
            }
        return {
            "arquivo": getattr(item, "file_name", ""),
            "categoria": getattr(item, "category", ""),
            "valor": float(getattr(item, "amount", 0) or 0),
            "status": getattr(item, "status", ""),
            "metodo": getattr(item, "method", ""),
        }

    itens_rec_dict  = [_para_dict(i) for i in itens_rec]
    itens_desp_dict = [_para_dict(i) for i in itens_desp]

    tot_rec  = sum(i["valor"] for i in itens_rec_dict)
    tot_desp = sum(i["valor"] for i in itens_desp_dict)
    rp = tot_rec - tot_desp  # RP = PenRec − PenAplic (negativo quando despesa > receita)

    logger.info(
        "[Conciliação] Receita=R$ %s | Despesa=R$ %s | RP=R$ %s",
        _num_br(tot_rec), _num_br(tot_desp), _num_br(rp),
    )

    with DatabasePMPV() as db:
        db.salvar_concilia_itens(periodo, itens_rec_dict + itens_desp_dict)
        db.atualizar_rp(periodo, rp)

    return {"periodo": periodo, "rp": rp, "n_itens": len(itens_rec_dict) + len(itens_desp_dict)}


def _etapa_pmpv(periodo: str, pasta: Path, cfg: dict, trimestre: list[str]) -> dict:
    """Lê Excel de Memória de Cálculo, calcula PMPV e salva no banco."""
    from Src.Services.servicos_pmpv import RegrasPMPV, ExcelPMPV
    from Src.Database.database import DatabasePMPV

    valor_cg = float(cfg.get("PMPV_VALOR_CG", "0.0"))

    # Seleciona o arquivo de Memória de Cálculo pelo trimestre do período.
    # Ordem de prioridade:
    #   1. PMPV_ARQUIVO_<TRIM> (ex: PMPV_ARQUIVO_NOV_JAN) — específico por trimestre
    #   2. PMPV_ARQUIVO — genérico (fallback para quem usa arquivo único)
    #   3. SUBPASTA_PMPV — busca dentro da pasta de entrada
    _TRIM_CHAVE = {
        "NOV_JAN": [10, 11, 0],
        "FEV_ABR": [1, 2, 3],
        "MAI_JUL": [4, 5, 6],
        "AGO_OUT": [7, 8, 9],
    }
    mes_abrev = periodo.split("/")[0]
    mes_idx = _MESES_ABREV.index(mes_abrev)
    chave_trim = next(
        (f"PMPV_ARQUIVO_{k}" for k, v in _TRIM_CHAVE.items() if mes_idx in v),
        "PMPV_ARQUIVO",
    )
    arquivo_direto = cfg.get(chave_trim, "").strip() or cfg.get("PMPV_ARQUIVO", "").strip()
    if chave_trim != "PMPV_ARQUIVO" and cfg.get(chave_trim, "").strip():
        logger.info("[PMPV] Usando chave %s para período %s", chave_trim, periodo)
    if arquivo_direto:
        arquivo_mc = Path(arquivo_direto)
        if not arquivo_mc.is_absolute():
            arquivo_mc = Path(__file__).parent / arquivo_mc
        if not arquivo_mc.exists():
            logger.warning("[PMPV] PMPV_ARQUIVO não encontrado: %s", arquivo_mc)
            return {"periodo": periodo, "pmpv": 0.0}
        logger.info("[PMPV] Usando PMPV_ARQUIVO: %s", arquivo_mc)
    else:
        if not pasta.exists():
            logger.warning("[PMPV] Pasta não encontrada: %s — pulando etapa", pasta)
            return {"periodo": periodo, "pmpv": 0.0}

        # Encontra o arquivo de Memória de Cálculo dentro da pasta
        arquivo_mc = None
        for caminho in pasta.rglob("*.xlsx"):
            nome = caminho.stem.upper()
            if any(p in nome for p in ("MEMORIA", "CALCULO", "MEM", "MC")):
                arquivo_mc = caminho
                break
        if not arquivo_mc:
            excels = list(pasta.rglob("*.xlsx"))
            arquivo_mc = excels[0] if excels else None

        if not arquivo_mc:
            logger.warning("[PMPV] Nenhum Excel encontrado em %s", pasta)
            return {"periodo": periodo, "pmpv": 0.0}

    logger.info("[PMPV] Arquivo: %s | Trimestre: %s", arquivo_mc.name, trimestre)

    dados_por_mes: dict = {}
    lista_meses: list[str] = []
    for mes in trimestre:
        try:
            dados = ExcelPMPV.ler_dados_memoria_calculo(arquivo_mc, mes)
            if dados:
                dados_por_mes[f"Mês {len(dados_por_mes)+1}"] = [
                    {
                        "empresa":    nome,
                        "molecula":   v.get("mol", 0),
                        "transporte": v.get("trans", 0),
                        "logistica":  v.get("log", 0),
                        "volume":     v.get("volume", 0),
                        "campos_vazios": [],
                    }
                    for nome, v in dados.items()
                ]
                lista_meses.append(mes)
        except Exception:
            logger.warning("[PMPV] Falha ao ler mês %s", mes, exc_info=True)

    if not dados_por_mes:
        logger.warning("[PMPV] Nenhum dado extraído")
        return {"periodo": periodo, "pmpv": 0.0}

    resultado = RegrasPMPV.calcular_resultados(
        dados_extraidos=dados_por_mes,
        valor_cg=valor_cg,
        dias_config={f"Mês {i+1}": 30 for i in range(len(dados_por_mes))},
        lista_meses=lista_meses,
        idx_start=0,
    )

    pmpv = resultado.get("pmpv", 0.0)
    logger.info(
        "[PMPV] PMPV = R$ %s/m³ | VP = %s m³",
        _num_br(pmpv, 4), _num_br(resultado.get("vp_mensal", 0)),
    )

    with DatabasePMPV() as db:
        db.salvar_pmpv_mensal(periodo, pmpv)

    return {"periodo": periodo, "pmpv": pmpv, "resultado_completo": resultado}


def _etapa_consolidar(periodo: str, resultados: dict) -> dict:
    """Junta todos os módulos: RPV = CGR − CGF | SCG = RPV + RET + RP."""
    from Src.Services.servicos_consolidacao import ServicosConsolidacao

    cgr     = resultados["auditoria"].get("cgr", 0.0)
    ret     = resultados["ret"].get("ret", 0.0)
    rp      = resultados["concilia"].get("rp", 0.0)
    pmpv    = resultados["pmpv"].get("pmpv", 0.0)
    vol_cgf = resultados["cgf"].get("volume_final", 0.0)

    # CGF em R$ = volume × PMPV (se PMPV disponível)
    cgf_valor = vol_cgf * pmpv if pmpv > 0 else vol_cgf

    rpv = cgr - cgf_valor
    scg = rpv + ret + rp

    logger.info(
        "[SCG] CGR=R$ %s | CGF=R$ %s | RPV=R$ %s | RET=R$ %s | RP=R$ %s | SCG=R$ %s",
        _num_br(cgr), _num_br(cgf_valor), _num_br(rpv), _num_br(ret), _num_br(rp), _num_br(scg),
    )

    srv = ServicosConsolidacao()
    try:
        # Cria o período se não existir ainda
        periodos_existentes = [p["periodo"] for p in srv.obter_periodos()]
        if periodo not in periodos_existentes:
            srv.criar_periodo(periodo)

        srv.repo.atualizar_campos_consolidacao(
            periodo,
            cgr=cgr, cgf=cgf_valor, ret=ret, rp=rp, rpv=rpv, scg=scg,
        )
    finally:
        srv.fechar()

    return {"periodo": periodo, "scg": scg, "rpv": rpv, "cgf_valor": cgf_valor}


def _etapa_excel(periodo: str, trimestre: list[str], cfg: dict) -> str:
    """Gera o Excel final consolidado na pasta de saída."""
    from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado
    from Src.common.excel_final_destino import EXCEL_FIXO_PATH

    pasta_saida = Path(cfg.get("PASTA_SAIDA", str(Path(__file__).parent / "saida")))
    pasta_saida.mkdir(parents=True, exist_ok=True)

    periodo_nome = periodo.replace("/", "-")
    nome_arquivo = str(pasta_saida / f"Relatorio_ContaGrafica_{periodo_nome}.xlsx")

    arquivo = ExcelConsolidado.exportar(
        periodo=periodo,
        nome_arquivo=nome_arquivo,
        periodos_trimestre=trimestre,
    )

    logger.info("[Excel] Gerado: %s", arquivo)
    return arquivo


# ── Validação (dry-run) ───────────────────────────────────────────────────────

def _validar_pastas(pasta_base: Path, cfg: dict) -> bool:
    """Verifica se as pastas de entrada existem e têm arquivos esperados."""
    ok = True
    checks = [
        ("CGR",  pasta_base / cfg.get("SUBPASTA_CGR", "CGR"),   "*.xml"),
        ("RET",  pasta_base / cfg.get("SUBPASTA_RET", "RET"),   "*.pdf"),
        ("CGF",  pasta_base / cfg.get("SUBPASTA_CGF", "CGF"),   "*.xlsx"),
        ("RP",   pasta_base / cfg.get("SUBPASTA_RP",  "RP"),    "*.pdf"),
        ("PMPV", pasta_base / cfg.get("SUBPASTA_PMPV","PMPV"),  "*.xlsx"),
    ]

    for nome, pasta, padrao in checks:
        if not pasta.exists():
            logger.warning("[Validação] AUSENTE  — %s (%s)", nome, pasta)
            ok = False
        else:
            arquivos = list(pasta.rglob(padrao))
            status = "OK" if arquivos else "VAZIA"
            logger.info("[Validação] %-8s — %s (%d arquivo(s))", status, nome, len(arquivos))
            if not arquivos:
                ok = False

    return ok


# ── Ponto de entrada principal ────────────────────────────────────────────────

def main(periodo: str | None = None,
         pasta_base: str | None = None,
         dry_run: bool = False) -> str | None:
    """
    Executa o pipeline completo.

    Args:
        periodo:    Período no formato 'Mai/2026'. Se None, usa o mês atual.
        pasta_base: Caminho da pasta raiz com os dados de entrada.
        dry_run:    Se True, só valida pastas/arquivos sem processar.

    Returns:
        Caminho do Excel gerado, ou None em dry-run.
    """
    configurar_logging()
    cfg = _carregar_config()

    periodo = periodo or _periodo_atual()
    trimestre = _trimestre_atual(periodo)

    pasta = Path(pasta_base or cfg.get("PASTA_ENTRADA", str(Path(__file__).parent / "dados" / "entrada")))

    logger.info("=" * 60)
    logger.info("PIPELINE GraphAccount Pro")
    logger.info("Período : %s", periodo)
    logger.info("Trimestre: %s", " | ".join(trimestre))
    logger.info("Pasta   : %s", pasta)
    logger.info("=" * 60)

    # ── dry-run: só valida ────────────────────────────────────────────────────
    if dry_run:
        logger.info("Modo DRY-RUN — nenhum dado será processado")
        ok = _validar_pastas(pasta, cfg)
        logger.info("Validação: %s", "OK" if ok else "PROBLEMAS ENCONTRADOS")
        return None

    # ── Import do notificador (tolerante a falha de config) ───────────────────
    try:
        from notificador import enviar_falha, enviar_sucesso
        _notificacao_ativa = True
    except Exception:
        logger.warning("Notificador não configurado — pipeline roda sem e-mail")
        _notificacao_ativa = False
        enviar_falha = enviar_sucesso = lambda *a, **k: None  # type: ignore

    resultados: dict = {}
    etapas_com_falha: list[str] = []

    # ── Etapas independentes — uma falha não impede as demais ────────────────
    # Cada módulo lê sua própria pasta; um PDF/XML corrompido num módulo não
    # deve impedir o processamento dos outros três.
    etapas_independentes = [
        ("auditoria", _etapa_auditoria, pasta / cfg.get("SUBPASTA_CGR", "CGR"), {"cgr": 0.0, "n_itens": 0}),
        ("ret",       _etapa_ret,       pasta / cfg.get("SUBPASTA_RET", "RET"), {"ret": 0.0, "n_itens": 0}),
        ("cgf",       _etapa_cgf,       pasta / cfg.get("SUBPASTA_CGF", "CGF"), {"volume_final": 0.0}),
        ("concilia",  _etapa_concilia,  pasta / cfg.get("SUBPASTA_RP",  "RP"),  {"rp": 0.0, "n_itens": 0}),
    ]

    for nome, fn, subpasta, fallback in etapas_independentes:
        try:
            resultados[nome] = fn(periodo, subpasta, cfg)
        except Exception:
            logger.exception("[%s] FALHOU — seguindo com as demais etapas", nome.upper())
            etapas_com_falha.append(nome)
            resultados[nome] = {"periodo": periodo, **fallback}

    # ── PMPV (precisa do trimestre) ───────────────────────────────────────────
    try:
        resultados["pmpv"] = _etapa_pmpv(
            periodo,
            pasta / cfg.get("SUBPASTA_PMPV", "PMPV"),
            cfg,
            trimestre,
        )
    except Exception:
        logger.exception("[PMPV] FALHOU")
        etapas_com_falha.append("pmpv")
        resultados["pmpv"] = {"periodo": periodo, "pmpv": 0.0}

    # ── Se alguma etapa falhou, o SCG ficaria incompleto/errado: aborta aqui ──
    if etapas_com_falha:
        logger.error("Pipeline interrompido — etapas com falha: %s", ", ".join(etapas_com_falha))
        logger.error("Excel final NÃO será gerado para evitar relatório com dados incompletos.")
        enviar_falha(etapas_com_falha, periodo)
        sys.exit(1)

    # ── Consolidação ──────────────────────────────────────────────────────────
    try:
        resultados["scg"] = _etapa_consolidar(periodo, resultados)
    except Exception:
        logger.exception("[SCG] FALHOU")
        enviar_falha("consolidação", periodo)
        sys.exit(1)

    # ── Excel Final ───────────────────────────────────────────────────────────
    try:
        arquivo = _etapa_excel(periodo, trimestre, cfg)
    except Exception:
        logger.exception("[Excel] FALHOU")
        enviar_falha("excel final", periodo)
        sys.exit(1)

    # ── Sucesso ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("PIPELINE CONCLUÍDO — %s", arquivo)
    logger.info("=" * 60)
    enviar_sucesso(periodo, arquivo, resultados)

    return arquivo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline de automação do fechamento mensal — GraphAccount Pro"
    )
    parser.add_argument("--periodo", default=None,
                        help="Período (ex: Mai/2026). Padrão: mês atual.")
    parser.add_argument("--pasta",   default=None,
                        help="Pasta raiz com os dados. Padrão: ./dados/entrada")
    parser.add_argument("--dry-run", action="store_true",
                        help="Valida pastas sem processar dados.")
    args = parser.parse_args()

    main(
        periodo=args.periodo,
        pasta_base=args.pasta,
        dry_run=args.dry_run,
    )
