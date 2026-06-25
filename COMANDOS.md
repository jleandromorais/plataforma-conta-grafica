# Comandos Rápidos - Plataforma Conta Gráfica

> ⚠️ Comandos que apontam para `backend/...` referem-se à stack **arquivada** em
> `_arquivado/backend/` (Airflow/Postgres descontinuado). Para automação atual, use
> `pipeline.py` — ver [COMO_USAR_AUTOMACAO.md](COMO_USAR_AUTOMACAO.md).

## 🚀 Inicialização

```powershell
# Opção 1: Script automático
python start.py

# Opção 2: Manual
docker-compose up -d
```

## 🔍 Verificação

```powershell
# Verificar setup
python check_setup.py

# Status dos containers
docker ps

# Logs do scheduler
docker logs airflow-scheduler --tail 50

# Logs do webserver
docker logs airflow-webserver --tail 50

# Logs do PostgreSQL
docker logs postgres-plataforma --tail 50
```

## 🧪 Testes

```powershell
# Testes unitários (pytest)
python -m pytest tests/test_dq_staging.py -v

# Teste de conexão PostgreSQL
python -c "from sqlalchemy import create_engine; engine=create_engine('postgresql+psycopg2://postgres:admin@localhost:5432/plataforma'); print('✅ Conectado!' if engine.connect() else '❌ Falhou')"

# Teste de export Excel local
python backend/reporting/export_excel.py
```

## 🔄 Gerenciamento

```powershell
# Parar tudo
docker-compose down

# Parar e limpar volumes (CUIDADO: apaga dados!)
docker-compose down -v

# Rebuild (após mudanças no código)
docker-compose build
docker-compose up -d

# Restart apenas um serviço
docker-compose restart airflow-scheduler

# Ver logs em tempo real
docker-compose logs -f airflow-scheduler
```

## 📊 Airflow Web UI

```
URL: http://localhost:8080
Login: airflow / airflow

Ações comuns:
- Ativar DAG: Toggle OFF→ON
- Rodar manualmente: Botão Play
- Ver logs: DAG → Task → View Log
- Pausar/Unpause: Toggle
```

## 📂 Pastas Importantes

```powershell
# Relatórios Excel gerados
ls reports/

# Logs de alertas
ls logs/

# DAGs do Airflow
ls backend/airflow/dags/

# Dados de entrada
ls backend/data/
```

## 🔧 Troubleshooting

```powershell
# Porta ocupada
docker-compose down -v
docker container prune -f

# DAG não aparece
docker logs airflow-scheduler | grep -i error

# Excel vazio
docker exec postgres-plataforma psql -U postgres -d plataforma -c "SELECT * FROM marts.visao_geral;"

# Reset completo
docker-compose down -v
docker volume prune -f
docker-compose up -d
```

## 📧 Configurar Email

```powershell
# 1. Editar backend/.env
notepad backend/.env

# 2. Configurar:
SMTP_HOST=smtp.gmail.com
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_app
ALERT_TO=destinatario@empresa.com

# 3. Restart
docker-compose restart
```

## ⏰ Mudar Horários

```powershell
# Editar DAG
notepad backend/airflow/dags/dag_export_excel.py

# Mudar schedule_interval
schedule_interval='0 8 * * *'  # 08:00 todo dia

# Airflow recarrega automaticamente em 1-2min
```

## 🎯 Comandos do Dia-a-Dia

```powershell
# De manhã: verificar se está rodando
docker ps

# Ver Excel do dia
ls reports/relatorio_geral_*.xlsx | sort -Descending | select -First 1

# Ver últimos alertas
docker logs postgres-plataforma --tail 20 | grep ALERTA

# Trigger manual de uma DAG
docker exec airflow-scheduler airflow dags trigger dag_export_excel
```
