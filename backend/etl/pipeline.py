from pathlib import Path

# CORREÇÃO: Adicionar 'backend.etl.' antes das pastas para o Python se encontrar
from backend.etl.extractors.pdf_extractor import extrair_pdf_ret
from backend.etl.transformers.ret_transform import transformar_ret
from backend.etl.loaders.postgres_loader import carregar_dados_postgres

def executar_pipeline_ret(pasta_origem: Path, empresa: str, periodo: str):
    print(f"\n--- Iniciando Linha de Montagem RET: {empresa} ({periodo}) ---")
    
    # 1. EXTRACT
    pdfs = list(pasta_origem.rglob("*.pdf"))
    if not pdfs:
        print(f"⚠️ Nenhum PDF encontrado na pasta: {pasta_origem}")
        return

    dados_brutos = [dado for pdf in pdfs if (dado := extrair_pdf_ret(pdf))]
    print(f"✅ Extrator: {len(dados_brutos)} ficheiros lidos.")

    # 2. TRANSFORM
    dados_limpos = [limpo for bruto in dados_brutos if (limpo := transformar_ret(bruto, empresa, periodo))]
    print(f"✅ Transformer: {len(dados_limpos)} registos processados.")

    # 3. LOAD (Agora aponta para o Postgres)
    sucesso = carregar_dados_postgres(
        nome_tabela="ret_itens", 
        dados_limpos=dados_limpos
    )
    
    if sucesso:
        print("🚀 Pipeline concluído! Dados perfeitamente guardados na base de dados.")
    else:
        print("❌ O Pipeline falhou na etapa de carregamento.")

if __name__ == "__main__":
    DIRETORIO_PDFS = Path(__file__).resolve().parent.parent.parent / "test_data" / "ret"
    
    # Garante que a pasta existe para não dar erro se estiver vazia
    DIRETORIO_PDFS.mkdir(parents=True, exist_ok=True)
    
    executar_pipeline_ret(DIRETORIO_PDFS, "PETROBRAS", "01/2026")