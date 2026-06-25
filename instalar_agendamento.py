"""
instalar_agendamento.py — Configura o Task Scheduler do Windows

Cria uma tarefa agendada que roda o pipeline.py automaticamente
todo dia 10 do mês às 08:00, sem precisar abrir nenhum programa.

Custo: R$ 0,00 — usa o agendador nativo do Windows.

Uso:
    python instalar_agendamento.py              # instala com padrões
    python instalar_agendamento.py --dia 5      # roda no dia 5 do mês
    python instalar_agendamento.py --hora 07:30 # roda às 07:30
    python instalar_agendamento.py --remover    # remove a tarefa

Requer execução como Administrador (clique direito → Executar como admin).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


NOME_TAREFA = "GraphAccountPro_Pipeline_Mensal"


def _python_atual() -> str:
    """Retorna o caminho do executável Python em uso."""
    return str(Path(sys.executable).resolve())


def _pipeline_path() -> str:
    """Retorna o caminho absoluto do pipeline.py."""
    return str(Path(__file__).parent / "pipeline.py")


def _projeto_dir() -> str:
    """Retorna o diretório raiz do projeto."""
    return str(Path(__file__).parent.resolve())


def instalar(dia: int = 10, hora: str = "08:00") -> bool:
    """
    Cria a tarefa no Task Scheduler do Windows.

    Args:
        dia:  Dia do mês para executar (1–28).
        hora: Horário no formato HH:MM.
    """
    python  = _python_atual()
    pipeline = _pipeline_path()
    diretorio = _projeto_dir()

    # Monta o comando que a tarefa vai executar
    # Redireciona saída para log diário (facilita depuração)
    log_path = str(Path(diretorio) / "logs" / "pipeline_agendado.log")
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    comando_acao = f'"{python}" "{pipeline}"'

    # XML da tarefa agendada — mais confiável que /SC MONTHLY via schtasks
    xml_tarefa = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Pipeline mensal do GraphAccount Pro — gera o fechamento automaticamente no dia {dia} de cada mes.</Description>
    <Author>GraphAccount Pro</Author>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2024-01-{dia:02d}T{hora}:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth>
          <Day>{dia}</Day>
        </DaysOfMonth>
        <Months>
          <January/>
          <February/>
          <March/>
          <April/>
          <May/>
          <June/>
          <July/>
          <August/>
          <September/>
          <October/>
          <November/>
          <December/>
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python}</Command>
      <Arguments>"{pipeline}"</Arguments>
      <WorkingDirectory>{diretorio}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    # Salva o XML temporariamente
    xml_path = Path(diretorio) / "logs" / "_tarefa_temp.xml"
    xml_path.write_text(xml_tarefa, encoding="utf-16")

    try:
        # Remove tarefa anterior se existir
        subprocess.run(
            ["schtasks", "/Delete", "/TN", NOME_TAREFA, "/F"],
            capture_output=True,
        )

        # Cria a tarefa via XML
        resultado = subprocess.run(
            ["schtasks", "/Create", "/TN", NOME_TAREFA, "/XML", str(xml_path), "/F"],
            capture_output=True,
            text=True,
        )

        if resultado.returncode == 0:
            print(f"✅ Tarefa '{NOME_TAREFA}' criada com sucesso!")
            print(f"   Executa todo dia {dia} do mês às {hora}")
            print(f"   Python : {python}")
            print(f"   Script : {pipeline}")
            print(f"   Pasta  : {diretorio}")
            print()
            print("Para verificar, abra o 'Agendador de Tarefas' do Windows")
            print("ou execute: schtasks /Query /TN", NOME_TAREFA)
            return True
        else:
            print("❌ Falha ao criar a tarefa:")
            print(resultado.stderr or resultado.stdout)
            print()
            print("Tente executar este script como Administrador:")
            print("  Clique direito no terminal → Executar como administrador")
            return False

    finally:
        xml_path.unlink(missing_ok=True)


def remover() -> bool:
    """Remove a tarefa agendada."""
    resultado = subprocess.run(
        ["schtasks", "/Delete", "/TN", NOME_TAREFA, "/F"],
        capture_output=True,
        text=True,
    )

    if resultado.returncode == 0:
        print(f"✅ Tarefa '{NOME_TAREFA}' removida.")
        return True
    else:
        print(f"⚠️  Tarefa não encontrada ou já removida.")
        return False


def verificar() -> None:
    """Exibe o status da tarefa agendada."""
    resultado = subprocess.run(
        ["schtasks", "/Query", "/TN", NOME_TAREFA, "/FO", "LIST"],
        capture_output=True,
        text=True,
        encoding="cp850",  # encoding do terminal Windows
    )

    if resultado.returncode == 0:
        print("📅 Status da tarefa agendada:")
        print(resultado.stdout)
    else:
        print(f"⚠️  Tarefa '{NOME_TAREFA}' não encontrada.")
        print("Execute 'python instalar_agendamento.py' para criar.")


def executar_agora() -> None:
    """Dispara o pipeline imediatamente (para testar)."""
    print("🚀 Executando o pipeline agora (modo teste)...")
    resultado = subprocess.run(
        [_python_atual(), _pipeline_path(), "--dry-run"],
        cwd=_projeto_dir(),
    )
    if resultado.returncode == 0:
        print("✅ Dry-run concluído sem erros. Pipeline está pronto.")
    else:
        print("❌ Erros encontrados. Verifique logs/app.log")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Configura o agendamento automático do pipeline no Windows Task Scheduler"
    )
    parser.add_argument("--dia",    type=int, default=10,
                        help="Dia do mês para executar (padrão: 10)")
    parser.add_argument("--hora",   default="08:00",
                        help="Horário no formato HH:MM (padrão: 08:00)")
    parser.add_argument("--remover", action="store_true",
                        help="Remove a tarefa agendada")
    parser.add_argument("--status",  action="store_true",
                        help="Mostra o status da tarefa")
    parser.add_argument("--testar",  action="store_true",
                        help="Executa o pipeline em modo dry-run agora")
    args = parser.parse_args()

    if args.remover:
        remover()
    elif args.status:
        verificar()
    elif args.testar:
        executar_agora()
    else:
        instalar(dia=args.dia, hora=args.hora)
