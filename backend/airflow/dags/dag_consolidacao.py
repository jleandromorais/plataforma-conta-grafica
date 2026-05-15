import logging
import sys
import os
from datetime import datetime
from airflow.decorators import dag, task

sys.path.append('/opt/airflow/backend')
from utils.db_utils import ler_staging, inserir_marts

@dag(
    dag_id="pipeline_consolidacao",
    schedule="0 0 * * 1",  # Toda segunda-feira a meia-noite
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "consolidacao"]
)
def dag_consolidacao():

    @task
    def ler_fontes_staging():
        try:
            logging.info("Lendo dados das tabelas staging para consolidacao.")
            fontes = {}
            for tabela in ["auditoria", "ret", "pmpv_agregados", "pmpv_empresas", "cgf", "concilia"]:
                try:
                    fontes[tabela] = ler_staging(tabela)
                except Exception:
                    fontes[tabela] = []
                    logging.warning(f"Tabela staging.{tabela} vazia ou indisponivel.")
            return fontes
        except Exception as e:
            logging.error(f"Falha ao orquestrar a leitura do staging: {str(e)}")
            raise

    @task
    def atualizar_marts_individuais(dados):
        try:
            periodo = datetime.now().strftime("%m/%Y")
            empresa = os.getenv("EMPRESA_PADRAO", "PETROBRAS")

            # marts.resumo_auditoria
            auditoria = dados.get("auditoria", [])
            if auditoria:
                resumo_aud = [{
                    "empresa": empresa,
                    "periodo": periodo,
                    "total_documentos": len(auditoria),
                    "valor_bruto_total": round(sum(float(i.get("valor_bruto", 0)) for i in auditoria), 2),
                    "cgr_liquido_total": round(sum(float(i.get("cgr_liquido", 0)) for i in auditoria), 2),
                }]
                inserir_marts("resumo_auditoria", resumo_aud)
                logging.info("marts.resumo_auditoria atualizado.")

            # marts.resumo_ret
            ret = dados.get("ret", [])
            if ret:
                resumo_ret = [{
                    "empresa": empresa,
                    "periodo": periodo,
                    "total_encargos": len(ret),
                    "valor_total_encargos": round(sum(float(i.get("valor_total", 0)) for i in ret), 2),
                }]
                inserir_marts("resumo_ret", resumo_ret)
                logging.info("marts.resumo_ret atualizado.")

            # marts.resumo_pmpv
            pmpv_ag = dados.get("pmpv_agregados", [])
            if pmpv_ag:
                ultimo = pmpv_ag[-1]
                resumo_pmpv = [{
                    "periodo": periodo,
                    "pmpv": round(float(ultimo.get("pmpv", 0)), 4),
                    "preco_final": round(float(ultimo.get("preco_final", 0)), 4),
                    "volume_total": round(float(ultimo.get("volume_total_vf", 0)), 4),
                    "custo_total": round(float(ultimo.get("custo_total", 0)), 2),
                }]
                inserir_marts("resumo_pmpv", resumo_pmpv)
                logging.info("marts.resumo_pmpv atualizado.")

            # marts.resumo_cgf
            cgf = dados.get("cgf", [])
            if cgf:
                ultimo_cgf = cgf[-1]
                resumo_cgf = [{
                    "periodo": periodo,
                    "volume_final_cgf": round(float(ultimo_cgf.get("volume_final_cgf", 0)), 4),
                    "total_faturado": round(float(ultimo_cgf.get("total_faturado_liquido", 0)), 4),
                    "total_canceladas": round(float(ultimo_cgf.get("total_canceladas", 0)), 4),
                    "total_devolucoes": round(float(ultimo_cgf.get("total_devolucoes", 0)), 4),
                }]
                inserir_marts("resumo_cgf", resumo_cgf)
                logging.info("marts.resumo_cgf atualizado.")

            # marts.resumo_concilia
            concilia = dados.get("concilia", [])
            if concilia:
                total_validados = sum(1 for d in concilia if d.get("status_conciliacao") == "VALIDADO")
                total_revisao = sum(1 for d in concilia if d.get("status_conciliacao") == "REVISAO_MANUAL")
                resumo_concilia = [{
                    "periodo": periodo,
                    "total_arquivos": len(concilia),
                    "total_validados": total_validados,
                    "total_revisao": total_revisao,
                    "valor_total_conciliado": round(sum(float(d.get("valor_conciliado", 0)) for d in concilia), 2),
                }]
                inserir_marts("resumo_concilia", resumo_concilia)
                logging.info("marts.resumo_concilia atualizado.")

            return dados
        except Exception as e:
            logging.error(f"Falha ao atualizar marts individuais: {str(e)}")
            raise

    @task
    def calcular_e_inserir_visao_geral(dados):
        try:
            logging.info("Calculando KPIs consolidados e inserindo em marts.visao_geral.")
            auditoria = dados.get("auditoria", [])
            ret = dados.get("ret", [])
            pmpv_ag = dados.get("pmpv_agregados", [])
            cgf = dados.get("cgf", [])
            periodo = datetime.now().strftime("%m/%Y")
            ultimo_pmpv = pmpv_ag[-1] if pmpv_ag else {}
            ultimo_cgf = cgf[-1] if cgf else {}

            kpis = [{
                "periodo": periodo,
                "pmpv": round(float(ultimo_pmpv.get("pmpv", 0.0)), 4),
                "cgr_liquido_total": round(sum(float(i.get("cgr_liquido", 0.0)) for i in auditoria), 2),
                "volume_cgf": round(float(ultimo_cgf.get("volume_final_cgf", 0.0)), 4),
                "valor_ret_total": round(sum(float(i.get("valor_total", 0.0)) for i in ret), 2),
            }]
            inserir_marts("visao_geral", kpis)
            logging.info("marts.visao_geral atualizado.")
        except Exception as e:
            logging.error(f"Falha ao inserir em marts.visao_geral: {str(e)}")
            raise

    fontes = ler_fontes_staging()
    marts_atualizados = atualizar_marts_individuais(fontes)
    calcular_e_inserir_visao_geral(marts_atualizados)

dag_instancia = dag_consolidacao()