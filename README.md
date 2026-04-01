# Plataforma Conta Gráfica - Data Engineering

Sistema completo de ETL, Data Warehouse, Data Quality e Relatórios automatizados.

## 🚀 Quick Start

### Pré-requisitos
- Docker Desktop instalado e rodando
- Python 3.10+ (para testes locais)
- 8GB RAM disponível

### Iniciar Sistema

```powershell
# 1. Subir todos os serviços
docker-compose up -d

# 2. Aguardar 2-3 minutos para inicialização

# 3. Acessar Airflow Web UI
http://localhost:8080
Login: airflow / airflow

# 4. Ativar DAGs (toggle ON)
- pipeline_auditoria_xml
- pipeline_ret_pdf
- pipeline_consolidacao
- dag_data_quality_diaria
- dag_export_excel
- dag_monitoramento_alertas
```

## 📊 Arquitetura

```
PostgreSQL (2 instâncias)
├─ airflow (metadata)
└─ plataforma (dados)
    ├─ raw (dados brutos)
    ├─ staging (dados limpos)
    └─ marts (dados agregados)

Apache Airflow
├─ 6 DAGs automatizadas
├─ Scheduler (24/7)
└─ Web UI (porta 8080)

Outputs
├─ reports/ (Excel diário)
└─ logs/ (alertas e auditoria)
```

## 🔄 DAGs e Horários

| DAG | Horário | Função |
|-----|---------|--------|
| `pipeline_auditoria_xml` | 00:00 diário | Processa XMLs fiscais |
| `pipeline_ret_pdf` | 00:00 diário | Processa PDFs de RET |
| `pipeline_consolidacao` | 00:00 seg | Consolida dados semanais |
| `dag_data_quality_diaria` | 02:30 diário | Testes de qualidade |
| `dag_monitoramento_alertas` | Cada 30min | Detecta anomalias |
| `dag_export_excel` | Semanal | Gera relatório Excel |

## 📁 Estrutura de Pastas

```
plataforma-conta-grafica/
├── backend/
│   ├── airflow/dags/        ← DAGs do Airflow
│   ├── data_quality/        ← Testes e validações
│   ├── etl/                 ← Extractors, Transformers, Loaders
│   ├── monitoring/          ← Alertas automáticos
│   ├── reporting/           ← Export Excel/PDF
│   └── warehouse/           ← Schema SQL
├── reports/                 ← Excel gerado automaticamente
├── logs/                    ← Logs do sistema
└── docker-compose.yml       ← Configuração Docker
```

## 🧪 Testes

```powershell
# Testes unitários
python -m pytest tests/test_dq_staging.py -v

# Testes locais
python backend/reporting/export_excel.py
```

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```bash
# PostgreSQL
PG_USER=postgres
PG_PASSWORD=admin
PG_HOST=localhost
PG_PORT=5432
PG_DB=plataforma

# SMTP (Alertas)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=seu_app_password
ALERT_FROM=seu_email@gmail.com
ALERT_TO=destinatario@empresa.com
```

### Mudar Horários das DAGs

Edite o arquivo da DAG:
```python
# backend/airflow/dags/dag_export_excel.py
schedule_interval='0 8 * * *'  # 08:00 todo dia
```

Formato cron:
- `0 8 * * *` = 08:00 todo dia
- `0 8 * * 1-5` = 08:00 seg-sex
- `*/30 * * * *` = A cada 30 minutos

## 📊 Verificar Resultados

```powershell
# Excel gerado
ls reports\relatorio_geral_*.xlsx

# Logs de alertas
cat logs\alerts_*.log

# Status dos containers
docker ps

# Logs do Airflow
docker logs airflow-scheduler --tail 100
```

## 🛠️ Troubleshooting

### Porta 5432 já em uso
```powershell
docker-compose down -v
docker container prune -f
docker-compose up -d
```

### DAG com erro de import
```powershell
docker logs airflow-scheduler --tail 200 | grep ERROR
```

### Excel vazio
Verificar se há dados em marts:
```powershell
docker exec postgres-plataforma psql -U postgres -d plataforma -c "SELECT COUNT(*) FROM marts.visao_geral;"
```

### Rebuild completo
```powershell
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## 📧 Configurar Alertas Gmail

1. Acesse: https://myaccount.google.com/
2. Segurança → Senhas de Aplicativo
3. Gere senha para "Mail"
4. Cole no `.env` em `SMTP_PASSWORD`

## 🎯 Passos Concluídos

✅ Passo 1: ETL Modular  
✅ Passo 2: PostgreSQL + Migração  
✅ Passo 3: Data Warehouse (raw, staging, marts)  
✅ Passo 4: Airflow Orchestration  
✅ Passo 5: Data Quality (pytest + SQL checks)  
✅ Passo 6: Excel Reporting  
✅ Passo 7: Alertas Automáticos  

## 📞 Suporte

Para dúvidas ou problemas, verifique logs:
- Airflow: `docker logs airflow-scheduler`
- PostgreSQL: `docker logs postgres-plataforma`
- DAG específica: Airflow Web UI → DAG → View Log
