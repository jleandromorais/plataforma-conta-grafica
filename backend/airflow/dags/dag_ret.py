import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from airflow.decorators import dag, task

sys.path.append('/opt/airflow/backend')
from utils.db_utils import inserir_marts
from etl.extractors.pdf_extractor import extrair_pdf_ret
from etl.transformers.ret_transform import transformar_ret
from etl.loaders.postgres_loader import carregar_dados_postgres

@dag(
    dag_id="pipeline_ret_pdf",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "ret"]
)
def dag_ret():

    @task
    def extrair_pdf():
        try:
            logging.info("Iniciando extracao de PDFs RET.")
            pasta_pdfs = Path(os.getenv("RET_PDF_DIR", "/opt/airflow/backend/data/pdfs"))
            if not pasta_pdfs.exists():
                logging.warning(f"Pasta de PDFs nao encontrada: {pasta_pdfs}")
                return []
            dados = []
            for caminho in pasta_pdfs.rglob("*.pdf"):
                bruto = extrair_pdf_ret(caminho)
                if bruto:
                    dados.append(bruto)
            logging.info(f"Total de PDFs extraidos: {len(dados)}")
            return dados
        except Exception as e:
            logging.error(f"Falha na extracao de PDFs: {str(e)}")
            raise

    @task
    def transformar_ret_task(dados_brutos):
        try:
            logging.info("Iniciando transformacao RET.")
            empresa = os.getenv("EMPRESA_PADRAO", "PETROBRAS")
            periodo = datetime.now().strftime("%m/%Y")
            dados_limpos = []
            for bruto in dados_brutos:
                limpo = transformar_ret(bruto, empresa=empresa, periodo=periodo)
                if limpo:
                    dados_limpos.append(limpo)
            logging.info(f"Total de registros RET transformados: {len(dados_limpos)}")
            return dados_limpos
        except Exception as e:
            logging.error(f"Falha na transformacao RET: {str(e)}")
            raise

    @task
    def carregar_staging_ret(dados_limpos):
        try:
            logging.info("Carregando dados em staging.ret.")
            carregar_dados_postgres("staging.ret", dados_limpos)
            return dados_limpos
        except Exception as e:
            logging.error(f"Falha na carga em staging.ret: {str(e)}")
            raise

    @task
    def agregar_marts_ret(dados_inseridos):
        try:
            logging.info("Agregando dados para marts.resumo_ret.")
            empresa = os.getenv("EMPRESA_PADRAO", "PETROBRAS")
            periodo = datetime.now().strftime("%m/%Y")
            resumo = [{
                "empresa": empresa,
                "periodo": periodo,
                "total_encargos": len(dados_inseridos),
                "valor_total_encargos": round(sum(float(item.get("valor_total", 0.0)) for item in dados_inseridos), 2)
            }]
            inserir_marts("resumo_ret", resumo)
        except Exception as e:
            logging.error(f"Falha na agregacao para marts.resumo_ret: {str(e)}")
            raise

    brutos = extrair_pdf()
    limpos = transformar_ret_task(brutos)
    inseridos = carregar_staging_ret(limpos)
    agregar_marts_ret(inseridos)

dag_instancia = dag_ret()