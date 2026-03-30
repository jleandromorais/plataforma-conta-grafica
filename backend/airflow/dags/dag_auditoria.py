import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from airflow.decorators import dag, task

# Adiciona o backend ao path do Python no Airflow para importar modulos do seu projeto
sys.path.append('/opt/airflow/backend')
from utils.db_utils import inserir_marts
from etl.extractors.xml_extractor import extrair_xml
from etl.transformers.auditoria_transform import transformar_auditoria
from etl.loaders.postgres_loader import carregar_dados_postgres

@dag(
    dag_id="pipeline_auditoria_xml",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "auditoria"]
)
def dag_auditoria():

    @task
    def extrair_dados():
        try:
            logging.info("Iniciando extracao de XMLs da pasta configurada.")
            pasta_xml = Path(os.getenv("AUDITORIA_XML_DIR", "/opt/airflow/backend/data/xmls"))
            if not pasta_xml.exists():
                logging.warning(f"Pasta de XMLs nao encontrada: {pasta_xml}")
                return []
            dados = []
            for caminho in pasta_xml.rglob("*.xml"):
                bruto = extrair_xml(caminho)
                if bruto:
                    dados.append(bruto)
            logging.info(f"Total de XMLs extraidos: {len(dados)}")
            return dados
        except Exception as e:
            logging.error(f"Falha na extracao de XMLs: {str(e)}")
            raise

    @task
    def transformar_dados(dados_brutos):
        try:
            logging.info("Iniciando transformacao de auditoria.")
            empresa = os.getenv("EMPRESA_PADRAO", "PETROBRAS")
            periodo = datetime.now().strftime("%m/%Y")
            dados_limpos = []
            for bruto in dados_brutos:
                limpo = transformar_auditoria(bruto, empresa)
                if limpo:
                    limpo["periodo"] = periodo
                    dados_limpos.append(limpo)
            logging.info(f"Total de registros transformados: {len(dados_limpos)}")
            return dados_limpos
        except Exception as e:
            logging.error(f"Falha na transformacao de auditoria: {str(e)}")
            raise

    @task
    def carregar_staging(dados_limpos):
        try:
            logging.info("Carregando dados limpos em staging.auditoria.")
            carregar_dados_postgres("staging.auditoria", dados_limpos)
            return dados_limpos
        except Exception as e:
            logging.error(f"Falha na carga em staging.auditoria: {str(e)}")
            raise

    @task
    def agregar_marts(dados_inseridos):
        try:
            logging.info("Agregando dados para marts.resumo_auditoria.")
            empresa = os.getenv("EMPRESA_PADRAO", "PETROBRAS")
            periodo = datetime.now().strftime("%m/%Y")
            resumo = [{
                "empresa": empresa,
                "periodo": periodo,
                "total_documentos": len(dados_inseridos),
                "valor_bruto_total": round(sum(float(item.get("valor_bruto", 0.0)) for item in dados_inseridos), 2),
                "cgr_liquido_total": round(sum(float(item.get("cgr_liquido", 0.0)) for item in dados_inseridos), 2)
            }]
            inserir_marts("resumo_auditoria", resumo)
        except Exception as e:
            logging.error(f"Falha na agregacao para marts.resumo_auditoria: {str(e)}")
            raise

    # Definicao do fluxo de dependencias
    brutos = extrair_dados()
    limpos = transformar_dados(brutos)
    inseridos = carregar_staging(limpos)
    agregar_marts(inseridos)

dag_instancia = dag_auditoria()