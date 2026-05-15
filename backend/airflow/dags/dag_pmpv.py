import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from airflow.decorators import dag, task

sys.path.append('/opt/airflow/backend')
from utils.db_utils import inserir_marts
from etl.extractors.excel_extractor import extrair_dados_excel
from etl.transformers.pmpv_transform import transformar_pmpv
from etl.loaders.postgres_loader import carregar_dados_postgres

@dag(
    dag_id="pipeline_pmpv",
    schedule="@monthly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "pmpv"]
)
def dag_pmpv():

    @task
    def extrair_excel():
        try:
            logging.info("Iniciando extracao de Excel PMPV.")
            pasta_excel = Path(os.getenv("PMPV_EXCEL_DIR", "/opt/airflow/backend/data/pmpv"))
            if not pasta_excel.exists():
                logging.warning(f"Pasta PMPV nao encontrada: {pasta_excel}")
                return {}
            dados_empresas = {}
            for caminho in pasta_excel.rglob("*.xlsx"):
                empresa = caminho.stem.upper()
                df = extrair_dados_excel(caminho, nome_aba=0)
                if df is not None and not df.empty:
                    dados_empresas[empresa] = df.to_dict(orient="records")
                    logging.info(f"Excel PMPV extraido: {caminho.name} ({len(dados_empresas[empresa])} linhas)")
            logging.info(f"Total de empresas extraidas: {len(dados_empresas)}")
            return dados_empresas
        except Exception as e:
            logging.error(f"Falha na extracao de Excel PMPV: {str(e)}")
            raise

    @task
    def transformar_pmpv_task(dados_brutos_empresas):
        try:
            logging.info("Iniciando transformacao PMPV.")
            if not dados_brutos_empresas:
                logging.warning("Nenhum dado PMPV para transformar.")
                return {"agregados": {}, "detalhes_empresas": []}

            valor_cg = float(os.getenv("PMPV_VALOR_CG", "0.0"))
            # dias_config: dicionario empresa -> dias faturamento
            dias_config = {}
            dias_env = os.getenv("PMPV_DIAS_CONFIG", "")
            if dias_env:
                for par in dias_env.split(","):
                    partes = par.strip().split("=")
                    if len(partes) == 2:
                        dias_config[partes[0].strip().upper()] = int(partes[1].strip())

            resultado = transformar_pmpv(dados_brutos_empresas, valor_cg=valor_cg, dias_config=dias_config)
            if resultado:
                logging.info(f"PMPV calculado: {resultado.get('agregados', {}).get('pmpv', 'N/A')}")
            return resultado or {"agregados": {}, "detalhes_empresas": []}
        except Exception as e:
            logging.error(f"Falha na transformacao PMPV: {str(e)}")
            raise

    @task
    def carregar_staging_pmpv(resultado):
        try:
            logging.info("Carregando dados em staging.pmpv_agregados e staging.pmpv_empresas.")
            periodo = datetime.now().strftime("%m/%Y")

            agregados = resultado.get("agregados", {})
            if agregados:
                agregados["periodo"] = periodo
                carregar_dados_postgres("staging.pmpv_agregados", [agregados])

            detalhes = resultado.get("detalhes_empresas", [])
            if detalhes:
                for item in detalhes:
                    item["periodo"] = periodo
                carregar_dados_postgres("staging.pmpv_empresas", detalhes)

            return resultado
        except Exception as e:
            logging.error(f"Falha na carga staging PMPV: {str(e)}")
            raise

    @task
    def agregar_marts_pmpv(resultado):
        try:
            logging.info("Agregando dados para marts.resumo_pmpv.")
            periodo = datetime.now().strftime("%m/%Y")
            agregados = resultado.get("agregados", {})
            resumo = [{
                "periodo": periodo,
                "pmpv": round(float(agregados.get("pmpv", 0.0)), 4),
                "preco_final": round(float(agregados.get("preco_final", 0.0)), 4),
                "volume_total": round(float(agregados.get("volume_total_vf", 0.0)), 4),
                "custo_total": round(float(agregados.get("custo_total", 0.0)), 2),
            }]
            inserir_marts("resumo_pmpv", resumo)
        except Exception as e:
            logging.error(f"Falha na agregacao marts.resumo_pmpv: {str(e)}")
            raise

    brutos = extrair_excel()
    resultado = transformar_pmpv_task(brutos)
    inserido = carregar_staging_pmpv(resultado)
    agregar_marts_pmpv(inserido)

dag_instancia = dag_pmpv()
