#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

caminho_env = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=caminho_env)

def configurar_warehouse():
    """Executa o SQL via docker exec + psql (evita encoding issues)."""
    
    caminho_sql = Path(__file__).parent / "create_schemas.sql"
    
    print("=== Iniciando configuracao do Data Warehouse ===\n")
    
    if not caminho_sql.exists():
        print(f"[ERRO] Arquivo nao encontrado: {caminho_sql}")
        return
    
    # Ler SQL
    try:
        conteudo_sql = caminho_sql.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        conteudo_sql = caminho_sql.read_text(encoding='cp1252')
    
    print(f"[OK] SQL lido ({len(conteudo_sql)} bytes)\n")
    
    # Executar via docker exec
    try:
        print("[EXECUTANDO] via docker exec postgres-plataforma psql...\n")
        
        result = subprocess.run(
            [
                "docker", "exec", "-i", "postgres-plataforma",
                "psql", "-U", "postgres", "-d", "plataforma"
            ],
            input=conteudo_sql,
            text=True,
            capture_output=True
        )
        
        if result.returncode == 0:
            print("[OK] Data Warehouse criado com sucesso!\n")
            print("=== SAIDA ===")
            if result.stdout:
                for linha in result.stdout.split('\n')[:50]:  # Primeiras 50 linhas
                    if linha.strip():
                        print(f"  {linha}")
        else:
            print(f"[ERRO] Falha na execucao:\n{result.stderr[:500]}")
            
    except FileNotFoundError:
        print("[ERRO] Docker nao encontrado. Instale Docker ou use setup_warehouse_local.py")
    except Exception as e:
        print(f"[ERRO] {type(e).__name__}: {e}")




if __name__ == "__main__":
    configurar_warehouse()
