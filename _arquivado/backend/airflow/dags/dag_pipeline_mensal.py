"""
DAG Orquestradora — Pipeline Mensal Conta Gráfica

Replica exatamente o que o usuário faz manualmente no programa desktop:
  1. Lê XMLs/PDFs/Excels das pastas
  2. Processa cada módulo (Auditoria, RET, CGF, Conciliação, PMPV)
  3. Salva tudo no SQLite (pmpv_data.db) — mesmo banco do programa
  4. Calcula SCG (RPV + RET + RP)
  5. Gera o Excel final idêntico ao do programa

Agendamento: Todo dia 10 do mês às 8h (Brasília = 11h UTC)
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task

sys.path.insert(0, '/opt/airflow/Src')
sys.path.insert(0, '/opt/airflow/backend')

default_args = {
    "owner": "conta-grafica",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

# Meses em PT-BR para normalização de período
_MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _periodo_atual() -> str:
    """Retorna período no formato do programa: 'Abr/26'"""
    now = datetime.now()
    return f"{_MESES_ABREV[now.month - 1]}/{str(now.year)[2:]}"


def _trimestre_atual() -> list[str]:
    """Retorna os 3 meses do trimestre no formato 'Abr/26'"""
    now = datetime.now()
    trimestre = []
    for i in range(2, -1, -1):
        mes_idx = (now.month - 1 - i) % 12
        ano = now.year if (now.month - 1 - i) >= 0 else now.year - 1
        trimestre.append(f"{_MESES_ABREV[mes_idx]}/{str(ano)[2:]}")
    return trimestre


@dag(
    dag_id="pipeline_mensal_conta_grafica",
    default_args=default_args,
    description="Substitui o trabalho manual: lê arquivos → processa → salva no SQLite → gera Excel",
    schedule="0 11 10 * *",  # Dia 10 às 8h Brasília (11h UTC)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["orquestrador", "mensal"],
)
def dag_pipeline_mensal():

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 1A — AUDITORIA XML
    # Lê XMLs de NF-e e CT-e, calcula CGR líquido, salva em auditoria_itens
    # ──────────────────────────────────────────────────────────────────────────
    @task
    def processar_auditoria():
        from Src.Services.servicos_auditoria import RegrasAuditoria
        from Src.Database.database import DatabasePMPV

        periodo = os.getenv("PERIODO_PROCESSO") or _periodo_atual()
        pasta = Path(os.getenv("AUDITORIA_XML_DIR",
                     "/opt/airflow/backend/data/SCG-26/RPV - Recuperação do Preço de Venda/CGR"))
        empresa = os.getenv("EMPRESA_PADRAO", "COPERGÁS")

        logging.info(f"[Auditoria] Período: {periodo} | Pasta: {pasta}")

        itens = []
        for caminho in pasta.rglob("*.xml"):
            try:
                tipo = RegrasAuditoria.detectar_tipo_xml(caminho)
                if tipo == "NF-e":
                    dados = RegrasAuditoria.parse_nfe(caminho)
                elif tipo == "CT-e":
                    dados = RegrasAuditoria.parse_cte(caminho)
                else:
                    continue
                if dados:
                    dados["empresa"] = empresa
                    dados["cgr_liquido"] = RegrasAuditoria.calcular_s_tributos(
                        dados.get("valor_total", 0),
                        dados.get("icms_taxa", 0)
                    )
                    itens.append(dados)
            except Exception as e:
                logging.warning(f"Erro ao processar {caminho.name}: {e}")

        logging.info(f"[Auditoria] {len(itens)} documentos processados")

        db = DatabasePMPV()
        try:
            db.salvar_auditoria_itens(periodo, itens)
            cgr_total = sum(i.get("cgr_liquido", 0) for i in itens)
            db.atualizar_cgr(periodo, cgr_total)
            logging.info(f"[Auditoria] CGR total: R$ {cgr_total:,.2f}")
        finally:
            db.fechar()

        return {"periodo": periodo, "n_itens": len(itens), "cgr": cgr_total}

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 1B — RET (Recuperação de Encargos de Transporte)
    # Lê PDFs de EAT/EC/Penalidades, calcula RET, salva em ret_itens
    # ──────────────────────────────────────────────────────────────────────────
    @task
    def processar_ret():
        from Src.Services.servicos_ret import RegrasRET
        from Src.Database.database import DatabasePMPV

        periodo = os.getenv("PERIODO_PROCESSO") or _periodo_atual()
        pasta = Path(os.getenv("RET_PDF_DIR",
                     "/opt/airflow/backend/data/SCG-26/RET - Recuperação de Encargos de Transporte"))

        logging.info(f"[RET] Período: {periodo} | Pasta: {pasta}")

        pdfs = list(pasta.rglob("*.pdf"))
        logging.info(f"[RET] {len(pdfs)} PDFs encontrados")

        itens = []
        for caminho in pdfs:
            try:
                dados = RegrasRET.extrair_dados_pdf(caminho)
                if dados:
                    itens.append(dados)
            except Exception as e:
                logging.warning(f"Erro ao processar {caminho.name}: {e}")

        resultado = RegrasRET.calcular_ret(itens) if itens else {"ret": 0}
        ret_total = resultado.get("ret", 0)
        logging.info(f"[RET] {len(itens)} itens | RET total: R$ {ret_total:,.2f}")

        db = DatabasePMPV()
        try:
            db.salvar_ret_itens(periodo, itens)
            db.atualizar_ret(periodo, ret_total)
        finally:
            db.fechar()

        return {"periodo": periodo, "n_itens": len(itens), "ret": ret_total}

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 1C — CGF (Volume Faturado)
    # Lê Excels de NF faturadas/canceladas/devoluções, calcula volume final
    # ──────────────────────────────────────────────────────────────────────────
    @task
    def processar_cgf():
        from Src.Services.servicos_cgf import ServicosCGF
        from Src.Database.database import DatabasePMPV

        periodo = os.getenv("PERIODO_PROCESSO") or _periodo_atual()
        pasta = Path(os.getenv("CGF_EXCEL_DIR",
                     "/opt/airflow/backend/data/SCG-26/RPV - Recuperação do Preço de Venda/CGF"))

        logging.info(f"[CGF] Período: {periodo} | Pasta: {pasta}")

        arquivos_fat, arquivos_canc, arquivos_dev = [], [], []
        for caminho in pasta.rglob("*.xlsx"):
            nome = caminho.stem.upper()
            if "CANCEL" in nome or "DENEGAD" in nome:
                arquivos_canc.append(caminho)
            elif "DEVOL" in nome:
                arquivos_dev.append(caminho)
            else:
                arquivos_fat.append(caminho)

        logging.info(f"[CGF] Faturadas:{len(arquivos_fat)} Canceladas:{len(arquivos_canc)} Devoluções:{len(arquivos_dev)}")

        resultado = ServicosCGF.calcular(
            arquivos_faturadas=arquivos_fat,
            arquivos_canceladas=arquivos_canc,
            arquivos_devolucoes=arquivos_dev,
        )

        vol_fat = resultado.get("volume_faturado", 0)
        vol_canc = resultado.get("volume_canceladas", 0)
        vol_dev = resultado.get("volume_devolucoes", 0)
        vol_proprio = resultado.get("volume_consumo_proprio", 0)
        vol_final = resultado.get("volume_final", 0)

        logging.info(f"[CGF] Volume final: {vol_final:,.4f} m³")

        db = DatabasePMPV()
        try:
            db.salvar_cgf_resumo(periodo, vol_fat, vol_canc, vol_dev, vol_proprio, vol_final)
            db.atualizar_cgf(periodo, vol_final)
        finally:
            db.fechar()

        return {"periodo": periodo, "volume_final": vol_final}

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 1D — CONCILIAÇÃO (RP)
    # Lê PDFs de Receita e Despesa, calcula RP líquido
    # ──────────────────────────────────────────────────────────────────────────
    @task
    def processar_concilia():
        from Src.Services.servicos_concilia import RegrasConcilia
        from Src.Database.database import DatabasePMPV

        periodo = os.getenv("PERIODO_PROCESSO") or _periodo_atual()
        pasta = Path(os.getenv("CONCILIA_PDF_DIR",
                     "/opt/airflow/backend/data/SCG-26/RP - Recuperação de Penalidades"))

        logging.info(f"[Conciliação] Período: {periodo} | Pasta: {pasta}")

        pdfs_receita, pdfs_despesa = [], []
        for caminho in pasta.rglob("*.pdf"):
            partes = [p.upper() for p in caminho.parts]
            if any("RECEITA" in p for p in partes):
                pdfs_receita.append(caminho)
            else:
                pdfs_despesa.append(caminho)

        logging.info(f"[Conciliação] Receita:{len(pdfs_receita)} Despesa:{len(pdfs_despesa)}")

        itens_receita = RegrasConcilia.processar_arquivos(pdfs_receita, "Receita") if pdfs_receita else []
        itens_despesa = RegrasConcilia.processar_arquivos(pdfs_despesa, "Despesa") if pdfs_despesa else []
        todos_itens = itens_receita + itens_despesa

        total_receita = sum(i.get("valor", 0) for i in itens_receita)
        total_despesa = sum(i.get("valor", 0) for i in itens_despesa)
        rp_total = total_receita - total_despesa

        logging.info(f"[Conciliação] Receita: R$ {total_receita:,.2f} | Despesa: R$ {total_despesa:,.2f} | RP: R$ {rp_total:,.2f}")

        db = DatabasePMPV()
        try:
            db.salvar_concilia_itens(periodo, todos_itens)
            db.atualizar_rp(periodo, rp_total)
        finally:
            db.fechar()

        return {"periodo": periodo, "n_itens": len(todos_itens), "rp": rp_total}

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 1E — PMPV (Preço Médio Ponderado de Venda)
    # Lê Excel de Memória de Cálculo, calcula PMPV trimestral
    # ──────────────────────────────────────────────────────────────────────────
    @task
    def processar_pmpv():
        from Src.Services.servicos_pmpv import RegrasPMPV, ExcelPMPV
        from Src.Database.database import DatabasePMPV

        periodo = os.getenv("PERIODO_PROCESSO") or _periodo_atual()
        pasta = Path(os.getenv("PMPV_EXCEL_DIR",
                     "/opt/airflow/backend/data/SCG-26/RPV - Recuperação do Preço de Venda"))
        valor_cg = float(os.getenv("PMPV_VALOR_CG", "0.0"))

        logging.info(f"[PMPV] Período: {periodo} | Pasta: {pasta}")

        # Procura o arquivo de Memória de Cálculo
        arquivo_mc = None
        for caminho in pasta.rglob("*.xlsx"):
            nome = caminho.stem.upper()
            if "MEM" in nome and "C" in nome or "MEMORIA" in nome or "CALCULO" in nome:
                arquivo_mc = caminho
                break
        # Fallback: qualquer xlsx na raiz da pasta
        if not arquivo_mc:
            excels = list(pasta.glob("*.xlsx"))
            if excels:
                arquivo_mc = excels[0]

        if not arquivo_mc:
            logging.warning("[PMPV] Arquivo de Memória de Cálculo não encontrado")
            return {"periodo": periodo, "pmpv": 0}

        logging.info(f"[PMPV] Usando arquivo: {arquivo_mc.name}")

        trimestre = _trimestre_atual()
        dados_por_mes = {}
        for mes in trimestre:
            try:
                dados = ExcelPMPV.ler_dados_memoria_calculo(arquivo_mc, mes)
                if dados:
                    dados_por_mes[mes] = dados
            except Exception as e:
                logging.warning(f"[PMPV] Erro ao ler mês {mes}: {e}")

        if not dados_por_mes:
            logging.warning("[PMPV] Nenhum dado extraído do Excel")
            return {"periodo": periodo, "pmpv": 0}

        resultado = RegrasPMPV.calcular_resultados(
            dados_extraidos=dados_por_mes,
            valor_cg=valor_cg,
            dias_config={},
            lista_meses=trimestre,
            idx_start=0,
        )

        pmpv = resultado.get("pmpv", 0)
        logging.info(f"[PMPV] PMPV calculado: R$ {pmpv:,.4f}/m³")

        db = DatabasePMPV()
        try:
            db.salvar_pmpv_mensal(periodo, pmpv)
        finally:
            db.fechar()

        return {"periodo": periodo, "pmpv": pmpv}

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 2 — CONSOLIDAÇÃO (SCG = RPV + RET + RP)
    # Junta todos os módulos e calcula o resultado final da Conta Gráfica
    # ──────────────────────────────────────────────────────────────────────────
    @task
    def consolidar(r_aud, r_ret, r_cgf, r_concilia, r_pmpv):
        from Src.Database.database import DatabasePMPV

        periodo = r_aud["periodo"]
        cgr = r_aud.get("cgr", 0)
        ret = r_ret.get("ret", 0)
        cgf_vol = r_cgf.get("volume_final", 0)
        rp = r_concilia.get("rp", 0)
        pmpv = r_pmpv.get("pmpv", 0)

        # CGF em R$ = volume_final × PMPV
        cgf_valor = cgf_vol * pmpv if pmpv > 0 else cgf_vol

        # RPV = CGR - CGF
        rpv = cgr - cgf_valor

        # SCG = RPV + RET + RP
        scg = rpv + ret + rp

        logging.info(f"[SCG] Período: {periodo}")
        logging.info(f"  CGR: R$ {cgr:,.2f}")
        logging.info(f"  CGF: R$ {cgf_valor:,.2f} (vol={cgf_vol:,.4f} × PMPV={pmpv:,.4f})")
        logging.info(f"  RPV: R$ {rpv:,.2f}")
        logging.info(f"  RET: R$ {ret:,.2f}")
        logging.info(f"  RP:  R$ {rp:,.2f}")
        logging.info(f"  SCG: R$ {scg:,.2f}")

        db = DatabasePMPV()
        try:
            db._garantir_periodo(periodo)
            db._update_consolidacao(periodo, cgr=cgr, cgf=cgf_valor, ret=ret, rp=rp)
            db.salvar_rpv(periodo, rpv)
            db.salvar_scg(periodo, scg)
        finally:
            db.fechar()

        return {"periodo": periodo, "scg": scg, "rpv": rpv}

    # ──────────────────────────────────────────────────────────────────────────
    # ETAPA 3 — GERAR EXCEL
    # Lê o SQLite atualizado e gera o Excel idêntico ao do programa
    # ──────────────────────────────────────────────────────────────────────────
    @task
    def gerar_excel(r_consolidacao):
        from reporting.export_excel import main as exportar

        periodo = r_consolidacao["periodo"]
        # Passa o período via env para o exportador usar o mês correto
        os.environ["EXPORT_PERIODO"] = periodo.replace("/", "/20") if len(periodo.split("/")[1]) == 2 \
            else periodo  # converte "Mai/26" → "Mai/2026"

        trimestre = _trimestre_atual()
        os.environ["EXPORT_TRIMESTRE"] = ",".join(
            p.replace("/", "/20") if len(p.split("/")[1]) == 2 else p
            for p in trimestre
        )

        caminho = exportar()
        logging.info(f"[Excel] Relatório gerado: {caminho}")
        return caminho

    # ──────────────────────────────────────────────────────────────────────────
    # FLUXO
    # ──────────────────────────────────────────────────────────────────────────
    r_aud = processar_auditoria()
    r_ret = processar_ret()
    r_cgf = processar_cgf()
    r_concilia = processar_concilia()
    r_pmpv = processar_pmpv()

    r_scg = consolidar(r_aud, r_ret, r_cgf, r_concilia, r_pmpv)

    gerar_excel(r_scg)


dag_instancia = dag_pipeline_mensal()
