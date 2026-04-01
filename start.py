"""
Script de Inicialização da Plataforma
Automatiza a inicialização completa do sistema
"""

import subprocess
import time
import sys

def run_command(cmd, description):
    """Executa comando e mostra resultado"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   PLATAFORMA CONTA GRÁFICA - INICIALIZAÇÃO AUTOMÁTICA   ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Passo 1: Verificar Docker
    if run_command("docker --version", "Verificando Docker") != 0:
        print("❌ Docker não está instalado ou não está no PATH!")
        sys.exit(1)
    
    # Passo 2: Parar containers existentes
    run_command("docker-compose down", "Parando containers existentes")
    
    # Passo 3: Subir serviços
    print("\n⏳ Subindo serviços... (aguarde 2-3 minutos)")
    if run_command("docker-compose up -d", "Iniciando Docker Compose") != 0:
        print("❌ Erro ao iniciar Docker Compose!")
        sys.exit(1)
    
    # Passo 4: Aguardar
    print("\n⏳ Aguardando inicialização dos containers...")
    for i in range(30, 0, -1):
        print(f"   {i} segundos restantes...", end='\r')
        time.sleep(1)
    print("\n")
    
    # Passo 5: Verificar status
    run_command("docker ps --format \"table {{.Names}}\\t{{.Status}}\"", "Status dos Containers")
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                    ✅ SISTEMA PRONTO!                    ║
    ╚══════════════════════════════════════════════════════════╝
    
    📊 Próximos Passos:
    
    1. Acesse o Airflow Web UI:
       http://localhost:8080
       Login: airflow / airflow
    
    2. Ative as 6 DAGs (clique nos toggles OFF→ON)
    
    3. Trigger cada DAG manualmente (botão play) nesta ordem:
       ① pipeline_auditoria_xml
       ② pipeline_ret_pdf
       ③ pipeline_consolidacao
       ④ dag_data_quality_diaria
       ⑤ dag_monitoramento_alertas
       ⑥ dag_export_excel
    
    4. Aguarde conclusão (~10 minutos)
    
    5. Verifique relatório:
       reports\\relatorio_geral_YYYYMMDD.xlsx
    
    ═══════════════════════════════════════════════════════════
    """)

if __name__ == "__main__":
    main()
