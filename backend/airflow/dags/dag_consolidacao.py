import logging
import sys
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
            
            # Tratamento individual para evitar falha geral se uma tabela estiver temporariamente vazia
            try:
                auditoria = ler_staging("auditoria")
            except Exception:
                auditoria = []
                
            try:
                ret = ler_staging("ret")
            except Exception:
                ret = []
                
            try:
                pmpv_agregados = ler_staging("pmpv_agregados")
            except Exception:
                pmpv_agregados = []

            try:
                cgf = ler_staging("cgf")
            except Exception:
                cgf = []

            return {
                "auditoria": auditoria,
                "ret": ret,
                "pmpv_agregados": pmpv_agregados,
                "cgf": cgf
            }
        except Exception as e:
            logging.error(f"Falha ao orquestrar a leitura do staging: {str(e)}")
            raise

    @task
    def calcular_kpis(dados):
        try:
            logging.info("Calculando KPIs consolidados.")
            auditoria = dados.get("auditoria", [])
            ret = dados.get("ret", [])
            pmpv_agregados = dados.get("pmpv_agregados", [])
            cgf = dados.get("cgf", [])

            ultimo_pmpv = pmpv_agregados[-1] if pmpv_agregados else {}
            periodo = datetime.now().strftime("%m/%Y")

            kpis = [{
                "periodo": periodo,
                "pmpv": round(float(ultimo_pmpv.get("pmpv", 0.0)), 4),
                "cgr_liquido_total": round(sum(float(item.get("cgr_liquido", 0.0)) for item in auditoria), 2),
                "volume_cgf": round(sum(float(item.get("volume_final_cgf", 0.0)) for item in cgf), 4),
                "valor_ret_total": round(sum(float(item.get("valor_total", 0.0)) for item in ret), 2)
            }]
            return kpis
        except Exception as e:
            logging.error(f"Falha ao calcular KPIs: {str(e)}")
            raise

    @task
    def inserir_visao_geral(kpis):
        try:
            logging.info("Inserindo resultados em marts.visao_geral.")
            inserir_marts("visao_geral", kpis)
        except Exception as e:
            logging.error(f"Falha ao inserir em marts.visao_geral: {str(e)}")
            raise

    fontes = ler_fontes_staging()
    kpis_calculados = calcular_kpis(fontes)
    inserir_visao_geral(kpis_calculados)

dag_instancia = dag_consolidacao()