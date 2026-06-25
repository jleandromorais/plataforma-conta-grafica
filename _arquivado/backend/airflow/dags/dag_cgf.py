import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from airflow.decorators import dag, task

sys.path.append('/opt/airflow/backend')
from utils.db_utils import inserir_marts
from etl.extractors.excel_extractor import extrair_dados_excel
from etl.transformers.cgf_transform import transformar_cgf
from etl.loaders.postgres_loader import carregar_dados_postgres

# Mapeamento padrão de colunas para o transformer CGF
CONFIGS_COLUNAS_PADRAO = {
    "volume": ["volume", "vol", "quantidade", "m3"],
    "tipo": ["tipo", "classificacao", "natureza"],
    "cliente": ["cliente", "consumidor", "empresa"],
    "nota": ["nota", "nf", "numero_nota", "num_nota"],
}

@dag(
    dag_id="pipeline_cgf",
    schedule="@monthly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "cgf"]
)
def dag_cgf():

    @task
    def extrair_excel():
        try:
            logging.info("Iniciando extracao de Excel CGF.")
            pasta_excel = Path(os.getenv("CGF_EXCEL_DIR", "/opt/airflow/backend/data/cgf"))
            if not pasta_excel.exists():
                logging.warning(f"Pasta CGF nao encontrada: {pasta_excel}")
                return []
            lista_dfs = []
            for caminho in pasta_excel.rglob("*.xlsx"):
                df = extrair_dados_excel(caminho, nome_aba=0)
                if df is not None and not df.empty:
                    # Detecta tipo pelo nome do arquivo
                    nome = caminho.stem.upper()
                    if "CANCEL" in nome or "DENEGAD" in nome:
                        tipo = "CANCELADA"
                    elif "DEVOL" in nome:
                        tipo = "DEVOLUCAO"
                    elif "COMPL" in nome:
                        tipo = "COMPLEMENTAR"
                    else:
                        tipo = "FATURADA"
                    lista_dfs.append({"tipo": tipo, "arquivo": str(caminho), "dados": df.to_dict(orient="records")})
                    logging.info(f"Excel CGF extraido: {caminho.name} (tipo={tipo}, {len(df)} linhas)")
            logging.info(f"Total de arquivos CGF extraidos: {len(lista_dfs)}")
            return lista_dfs
        except Exception as e:
            logging.error(f"Falha na extracao Excel CGF: {str(e)}")
            raise

    @task
    def transformar_cgf_task(lista_dfs_classificados):
        try:
            logging.info("Iniciando transformacao CGF.")
            if not lista_dfs_classificados:
                logging.warning("Nenhum dado CGF para transformar.")
                return {}
            resultado = transformar_cgf(lista_dfs_classificados, configs_colunas=CONFIGS_COLUNAS_PADRAO)
            if resultado:
                logging.info(f"CGF calculado: volume_final={resultado.get('volume_final_cgf', 'N/A')}")
            return resultado or {}
        except Exception as e:
            logging.error(f"Falha na transformacao CGF: {str(e)}")
            raise

    @task
    def carregar_staging_cgf(resultado):
        try:
            logging.info("Carregando dados em staging.cgf.")
            if not resultado:
                logging.warning("Resultado CGF vazio, nada a carregar.")
                return resultado
            periodo = datetime.now().strftime("%m/%Y")
            resultado["periodo"] = periodo
            carregar_dados_postgres("staging.cgf", [resultado])
            return resultado
        except Exception as e:
            logging.error(f"Falha na carga staging.cgf: {str(e)}")
            raise

    @task
    def agregar_marts_cgf(resultado):
        try:
            logging.info("Agregando dados para marts.resumo_cgf.")
            periodo = datetime.now().strftime("%m/%Y")
            resumo = [{
                "periodo": periodo,
                "volume_final_cgf": round(float(resultado.get("volume_final_cgf", 0.0)), 4),
                "total_faturado": round(float(resultado.get("total_faturado_liquido", 0.0)), 4),
                "total_canceladas": round(float(resultado.get("total_canceladas", 0.0)), 4),
                "total_devolucoes": round(float(resultado.get("total_devolucoes", 0.0)), 4),
            }]
            inserir_marts("resumo_cgf", resumo)
        except Exception as e:
            logging.error(f"Falha na agregacao marts.resumo_cgf: {str(e)}")
            raise

    brutos = extrair_excel()
    resultado = transformar_cgf_task(brutos)
    inserido = carregar_staging_cgf(resultado)
    agregar_marts_cgf(inserido)

dag_instancia = dag_cgf()
