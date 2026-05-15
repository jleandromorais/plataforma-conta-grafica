import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from airflow.decorators import dag, task

sys.path.append('/opt/airflow/backend')
from utils.db_utils import inserir_marts
from etl.extractors.pdf_extractor import extrair_pdf_concilia
from etl.transformers.concilia_transform import transformar_concilia
from etl.loaders.postgres_loader import carregar_dados_postgres

@dag(
    dag_id="pipeline_conciliacao",
    schedule="@monthly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "conciliacao"]
)
def dag_concilia():

    @task
    def extrair_pdfs():
        try:
            logging.info("Iniciando extracao de PDFs Conciliacao.")
            pasta_pdfs = Path(os.getenv("CONCILIA_PDF_DIR", "/opt/airflow/backend/data/conciliacao"))
            if not pasta_pdfs.exists():
                logging.warning(f"Pasta Conciliacao nao encontrada: {pasta_pdfs}")
                return []
            dados = []
            for caminho in pasta_pdfs.rglob("*.pdf"):
                bruto = extrair_pdf_concilia(caminho)
                if bruto:
                    dados.append(bruto)
                    logging.info(f"PDF conciliacao extraido: {caminho.name}")
            logging.info(f"Total de PDFs conciliacao extraidos: {len(dados)}")
            return dados
        except Exception as e:
            logging.error(f"Falha na extracao PDFs Conciliacao: {str(e)}")
            raise

    @task
    def transformar_concilia_task(dados_brutos):
        try:
            logging.info("Iniciando transformacao Conciliacao.")
            dados_limpos = []
            for bruto in dados_brutos:
                # Detecta categoria pelo campo arquivo_origem ou tipo no dado bruto
                categoria = bruto.get("categoria", "RP")
                limpo = transformar_concilia(bruto, categoria=categoria)
                if limpo:
                    dados_limpos.append(limpo)
            logging.info(f"Total de registros Conciliacao transformados: {len(dados_limpos)}")
            return dados_limpos
        except Exception as e:
            logging.error(f"Falha na transformacao Conciliacao: {str(e)}")
            raise

    @task
    def carregar_staging_concilia(dados_limpos):
        try:
            logging.info("Carregando dados em staging.concilia.")
            periodo = datetime.now().strftime("%m/%Y")
            for item in dados_limpos:
                item["periodo"] = periodo
            carregar_dados_postgres("staging.concilia", dados_limpos)
            return dados_limpos
        except Exception as e:
            logging.error(f"Falha na carga staging.concilia: {str(e)}")
            raise

    @task
    def agregar_marts_concilia(dados_inseridos):
        try:
            logging.info("Agregando dados para marts.resumo_concilia.")
            periodo = datetime.now().strftime("%m/%Y")
            total_validados = sum(1 for d in dados_inseridos if d.get("status_conciliacao") == "VALIDADO")
            total_revisao = sum(1 for d in dados_inseridos if d.get("status_conciliacao") == "REVISAO_MANUAL")
            valor_total = sum(float(d.get("valor_conciliado", 0.0)) for d in dados_inseridos)
            resumo = [{
                "periodo": periodo,
                "total_arquivos": len(dados_inseridos),
                "total_validados": total_validados,
                "total_revisao": total_revisao,
                "valor_total_conciliado": round(valor_total, 2),
            }]
            inserir_marts("resumo_concilia", resumo)
        except Exception as e:
            logging.error(f"Falha na agregacao marts.resumo_concilia: {str(e)}")
            raise

    brutos = extrair_pdfs()
    limpos = transformar_concilia_task(brutos)
    inseridos = carregar_staging_concilia(limpos)
    agregar_marts_concilia(inseridos)

dag_instancia = dag_concilia()
