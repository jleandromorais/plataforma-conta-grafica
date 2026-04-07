# Plataforma Conta Grafica

Automacao de auditoria fiscal para processamento de XML/PDF, consolidacao de dados e geracao de relatorios (CGR / RPV / RET / PMPV).

## O que este projeto faz

- Processa notas fiscais (NF-e e CT-e) por XML e PDF (OCR).
- Apura valores com e sem tributos com regras de negocio da conta grafica.
- Gera relatorios Excel consolidados para analise operacional.
- Disponibiliza pipelines de dados (ETL + Airflow) para execucao recorrente.

## Estrutura do repositorio

```
plataforma-conta-grafica/
├── Src/                      # Aplicacao principal (UI, servicos, dominio)
│   ├── Views/
│   ├── Services/
│   ├── Modules/
│   └── infrastructure/
├── backend/                  # ETL, Airflow, qualidade e monitoramento
│   ├── airflow/
│   ├── etl/
│   ├── data_quality/
│   ├── monitoring/
│   └── reporting/
├── tests/                    # Testes automatizados
├── config/
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Requisitos

- Python 3.10+
- Docker Desktop (opcional, para stack completa com Airflow/Postgres)

## Configuracao local

1. Crie e ative ambiente virtual.
2. Instale dependencias.
3. Copie `.env.example` para `.env` e ajuste variaveis.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Execucao

### Aplicacao desktop

```powershell
python start.py
```

### Stack de dados com Docker

```powershell
docker-compose up -d
```

Airflow Web UI:

- URL: http://localhost:8080
- Usuario: airflow
- Senha: airflow

## Testes

```powershell
python -m pytest -q
```

## Publicacao no GitHub (checklist)

- [x] Arquivos locais/sensiveis ignorados no `.gitignore`.
- [x] Exemplo de variaveis em `.env.example`.
- [x] README com setup e execucao.
- [ ] Remover do indice git arquivos grandes ja versionados anteriormente.
- [ ] Rotacionar chaves de API se alguma chave real ja foi exposta.

## Observacoes importantes

- Nunca commitar `.env` real.
- Nunca commitar bancos locais (`*.db`) e arquivos de entrada grandes (`*.zip`, `*.rar`).
- O fallback Gemini para OCR depende de quota/billing no projeto Google API.

## Licenca

Defina a licenca antes de publicar (sugestao: MIT).
