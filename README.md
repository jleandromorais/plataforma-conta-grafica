<div align="center">

# Plataforma Conta Gráfica

**Sistema integrado de gestão financeira para apuração de Conta Gráfica do setor regulado de gás canalizado**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-2B2B2B?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/DB-SQLite-003B57?logo=sqlite&logoColor=white)
![Airflow](https://img.shields.io/badge/Orquestração-Airflow-017CEE?logo=apacheairflow&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/DW-PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Testes](https://img.shields.io/badge/Testes-pytest-0A9EDC?logo=pytest&logoColor=white)

</div>

---

## Índice

- [Visão Geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Módulos da Aplicação](#módulos-da-aplicação)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Como Executar](#como-executar)
- [Fluxo de Operação](#fluxo-de-operação)
- [Banco de Dados](#banco-de-dados)
- [Backend (Airflow + PostgreSQL)](#backend-airflow--postgresql)
- [Testes](#testes)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Troubleshooting](#troubleshooting)
- [Contribuição](#contribuição)

---

## Visão Geral

Aplicação desktop Windows para apuração completa de **Conta Gráfica** do mercado regulado de gás, com 8 módulos especializados que calculam e consolidam componentes financeiros (PMPV, CGR, CGF, RET, RPV, SR, SCG) em um relatório Excel final unificado.

O repositório também inclui uma stack de **backend** com Apache Airflow e PostgreSQL para automação de ETL, validação de qualidade de dados e geração de relatórios agendados.

### Números do Projeto

| Métrica | Valor |
|---------|-------|
| Arquivos Python | 84+ |
| Telas da UI | 8 módulos |
| Serviços de negócio | 12 |
| Tabelas no banco | 12 |
| Testes automatizados | 11 arquivos |
| DAGs Airflow | 6 |
| Componentes ETL | 10 (3 extractors, 5 transformers, 2 loaders) |

---

## Funcionalidades

### Aplicação Desktop

- **PMPV** — Cálculo de Preço Médio Ponderado por Volume (trimestral) a partir de planilhas de moléculas, transporte e logística
- **Auditoria XML** — Processamento de NF-e/CT-e para apuração do CGR (Conta Gráfica de Receita) com cálculo de ICMS, PIS e COFINS
- **CGF** — Apuração de Volume Faturado (cancelamentos, devoluções, consumo próprio)
- **RET** — Recuperação de Encargos de Transporte (EAT, EC, TOP, Penalidades) a partir de PDFs
- **Conciliação RP** — Processamento de PDFs de receitas/despesas com suporte a OCR
- **RPV** — Cálculo automático: `RPV = CGR − CGF`
- **SR** — Receita Suplementar: `SR = (VP − VF) × PR`
- **SCG** — Saldo consolidado: `SCG = RPV + RET + RP`
- **Excel Final (Módulo 9)** — Exportação consolidada com controle de sessões e execuções por período

### Backend

- **ETL** — Pipelines para extração (Excel, PDF, XML), transformação e carga (PostgreSQL/SQLite)
- **Data Quality** — Validações SQL configuráveis via YAML com thresholds e alertas
- **Monitoramento** — Detecção de anomalias (falhas de qualidade, atrasos de importação, duplicatas, volumes zerados)
- **Relatórios** — Geração agendada de Excel consolidado via Airflow
- **Alertas** — Notificações por e-mail com templates HTML

---

## Arquitetura

```
plataforma-conta-grafica/
│
├── main.py                          # Entry point da aplicação desktop
├── start.py                         # Bootstrap da stack Docker
│
├── Src/                             # Aplicação desktop
│   ├── main_dashboard.py            # Janela principal (PlataformaFinanceira)
│   ├── Views/                       # 8 telas CustomTkinter
│   ├── Services/                    # Regras de negócio por módulo
│   ├── Database/                    # Persistência SQLite (DatabasePMPV)
│   ├── application/                 # Casos de uso (Clean Architecture)
│   ├── domain/                      # Contratos e interfaces (ports)
│   ├── infrastructure/              # Exportadores Excel, OCR, repositórios
│   ├── common/                      # Utilitários (normalização de período, UI)
│   ├── config/                      # Tema e configurações visuais
│   └── assets/                      # Ícones da aplicação
│
├── backend/                         # Stack de dados
│   ├── airflow/                     # Dockerfile + 6 DAGs
│   ├── etl/                         # Extractors, Transformers, Loaders
│   ├── data_quality/                # Validações SQL + YAML config
│   ├── monitoring/                  # Detector de anomalias + alertas
│   ├── reporting/                   # Geração de relatórios Excel
│   ├── warehouse/                   # Setup do data warehouse
│   └── migrations/                  # Migração SQLite → PostgreSQL
│
├── tests/                           # Testes automatizados (pytest)
├── docker-compose.yml               # 5 serviços (2 Postgres, 3 Airflow)
└── requirements.txt                 # Dependências Python
```

### Camadas e fluxo de dados

```
┌─────────────────────────────────────────────────────┐
│                    Views (CTk)                      │
│  PMPV │ Auditoria │ CGF │ RET │ Concilia │ RPV/SR  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                   Services                          │
│  Regras de negócio, cálculos, formatação BRL        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Infrastructure / Database              │
│  SQLite (local) │ Exportadores Excel │ OCR/Gemini   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│               Backend (opcional)                    │
│  Airflow DAGs → ETL → PostgreSQL → Relatórios       │
└─────────────────────────────────────────────────────┘
```

---

## Módulos da Aplicação

| # | Módulo | Fórmula / Lógica | Entrada | Saída |
|---|--------|------------------|---------|-------|
| 1 | **PMPV** | Preço Médio Ponderado por Volume (trimestral) | Planilhas Excel | PMPV R$/m³ por período |
| 2 | **Conciliação RP** | Consolidação receitas × despesas | PDFs (com OCR) | Itens conciliados |
| 3 | **RET** | Recuperação de Encargos de Transporte | Pasta de PDFs | Classificação EAT/EC/TOP/Penalidades |
| 4 | **Auditoria XML** | `CGR = (Σ valor − Σ ICMS) × (1 − PIS − COFINS)` | XML NF-e/CT-e | CGR líquido por empresa |
| 5 | **CGF** | Volume Faturado − Cancelados − Devoluções − Consumo próprio | Excel/CSV | Volume final faturado |
| 6 | **RPV** | `RPV = CGR − CGF` | Dados do banco | Saldo RPV |
| 7 | **SR** | `SR = (VP − VF) × PR` | Sessões PMPV | Receita suplementar |
| 8 | **SCG** | `SCG = RPV + RET + RP` | Todos os módulos | Saldo Conta Gráfica |
| 9 | **Excel Final** | Consolidação de todas as etapas | Banco de dados | `.xlsx` unificado |

---

## Pré-requisitos

| Requisito | Versão | Obrigatório |
|-----------|--------|:-----------:|
| Windows | 10/11 | Sim |
| Python | 3.10+ | Sim |
| PowerShell | 5.1+ | Sim |
| Docker Desktop | 4.0+ | Não* |

> \* Docker é necessário apenas para a stack de backend (Airflow + PostgreSQL). A aplicação desktop funciona de forma independente com SQLite local.

---

## Instalação

### 1. Clonar o repositório

```powershell
git clone https://github.com/jleandromorais/plataforma-conta-grafica.git
cd plataforma-conta-grafica
```

### 2. Criar e ativar ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependências

```powershell
pip install -r requirements.txt
```

### 4. (Opcional) Gerar executável `.exe`

```powershell
pyinstaller --noconfirm --clean --windowed --name PlataformaFinanceira main.py
```

O executável será gerado em `dist/PlataformaFinanceira/PlataformaFinanceira.exe`.

---

## Como Executar

### Aplicação Desktop

```powershell
python main.py
```

A janela principal abre com menu lateral contendo todos os 9 módulos.

### Stack Backend (Docker)

```powershell
# Inicialização automática
python start.py

# Ou manualmente
docker-compose up -d
```

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| Airflow Web UI | http://localhost:8080 | `airflow` / `airflow` |
| PostgreSQL (dados) | `localhost:5432` | `postgres` / `admin` |

---

## Fluxo de Operação

```
   ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────┐
   │  PMPV   │    │ Auditoria│    │   CGF   │    │   RET   │
   │ (Excel) │    │  (XML)   │    │(Excel)  │    │ (PDFs)  │
   └────┬────┘    └────┬─────┘    └────┬────┘    └────┬────┘
        │              │              │              │
        │              └──────┬───────┘              │
        │                     │                      │
        │              ┌──────▼──────┐               │
        │              │  RPV=CGR−CGF │               │
        │              └──────┬──────┘               │
        │                     │                      │
   ┌────▼────┐         ┌─────▼──────┐          ┌────▼────┐
   │   SR    │         │    SCG     │          │Concilia │
   │(VP−VF)×PR│        │RPV+RET+RP │          │  (RP)   │
   └────┬────┘         └─────┬──────┘          └────┬────┘
        │                    │                      │
        └────────────────────┼──────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Excel Final    │
                    │  (Módulo 9)     │
                    └─────────────────┘
```

### Passo a passo

1. Abra a aplicação com `python main.py`
2. Processe cada módulo para o período desejado (ex: `Dez/2025`)
3. Em cada módulo, clique em **"Adicionar ao Excel Final (Módulo 9)"**
4. Selecione ou crie uma sessão de destino no modal
5. Após processar todos os módulos, gere o Excel consolidado no **Módulo 9**

> **Importante:** Todos os períodos são normalizados automaticamente (`Dez/25` → `Dez/2025`) para evitar fragmentação de dados.

---

## Banco de Dados

A persistência local usa **SQLite** (`pmpv_data.db`) com 12 tabelas:

| Tabela | Descrição |
|--------|-----------|
| `sessoes` | Sessões PMPV (nome, datas, observações) |
| `dados_mes` | Dados mensais por sessão (empresa, moléculas, transporte, logística, volume) |
| `resultados` | Resultados calculados (PMPV, conta gráfica, preço final) |
| `pmpv_mensal` | PMPV R$/m³ por período |
| `auditoria_itens` | Itens de auditoria NF-e/CT-e (valor, ICMS, PIS, COFINS, CGR) |
| `ret_itens` | Encargos de transporte (tipo, empresa, valor, moeda) |
| `concilia_itens` | Itens de conciliação receita/despesa |
| `cgf_resumo` | Resumo de volumes faturados por período |
| `sr_resultados` | Resultados SR por período |
| `consolidacao` | Consolidação final (CGR, CGF, RPV, RET, RP, SCG) |
| `excel_final_sessoes` | Sessões de exportação Excel |
| `excel_final_execucoes` | Log de execuções de exportação |

### Normalização de períodos

O sistema normaliza automaticamente variantes de período:

```
Dez/25  →  Dez/2025
DEZ/25  →  Dez/2025
12/25   →  Dez/2025
```

Isso garante que consultas e consolidações sempre encontrem os dados corretos, independente do formato digitado pelo usuário.

---

## Backend (Airflow + PostgreSQL)

### Serviços Docker

| Serviço | Imagem | Porta | Função |
|---------|--------|-------|--------|
| `postgres` | `postgres:13` | — | Metadados do Airflow |
| `postgres-data` | `postgres:13` | `5432` | Data warehouse da aplicação |
| `airflow-webserver` | Custom | `8080` | Interface web do Airflow |
| `airflow-scheduler` | Custom | — | Agendador de DAGs |
| `airflow-init` | Custom | — | Inicialização (migração + admin) |

### DAGs disponíveis

| DAG | Função |
|-----|--------|
| `pipeline_auditoria_xml` | ETL de XMLs de auditoria |
| `pipeline_ret_pdf` | ETL de PDFs do RET |
| `pipeline_consolidacao` | Consolidação de dados |
| `dag_data_quality_diaria` | Validação de qualidade de dados |
| `dag_monitoramento_alertas` | Detecção de anomalias + alertas |
| `dag_export_excel` | Geração de relatório Excel |

### Pipeline ETL

```
Extractors              Transformers              Loaders
─────────────          ──────────────            ────────────
excel_extractor   →    pmpv_transform      →    postgres_loader
pdf_extractor     →    auditoria_transform →    sqlite_loader
xml_extractor     →    cgf_transform
                       concilia_transform
                       ret_transform
```

### Data Quality

Validações configuráveis via `dq_config.yaml`:

- **SQL checks** — Consultas que retornam linhas com falha (status `FAIL` se houver resultados)
- **Threshold checks** — Métricas escalares comparadas contra limites (`<=` ou `>=`)

### Monitoramento

O `AnomalyDetector` verifica 5 tipos de anomalia no PostgreSQL:

1. Falhas de qualidade de dados nas últimas 24h
2. Atraso de importação superior a 3 dias
3. Volume CGF zerado ou nulo
4. Períodos duplicados
5. Taxa de rejeição anormal

---

## Testes

### Executar suite completa

```powershell
python -m pytest
```

### Executar testes específicos

```powershell
# Testes do banco de dados
python -m pytest tests/test_database.py -v

# Testes do fluxo Excel Final
python -m pytest tests/test_excel_final_flow.py tests/test_excel_consolidado_none.py -v

# Testes de serviços de consolidação
python -m pytest tests/test_servicos_consolidacao.py -v

# Testes com cobertura
python -m pytest --cov=Src --cov-report=html
```

### Arquivos de teste

| Arquivo | Cobertura |
|---------|-----------|
| `test_database.py` | Persistência SQLite, normalização de períodos, exclusão em cascata |
| `test_servicos_consolidacao.py` | Regras de consolidação SCG |
| `test_servicos_cgf.py` | Cálculos de volume CGF |
| `test_pmpv_use_cases.py` | Casos de uso PMPV |
| `test_regras_pmpv.py` | Regras de negócio PMPV |
| `test_excel_handler.py` | Leitura/escrita Excel |
| `test_excel_final_flow.py` | Fluxo completo do Módulo 9 |
| `test_excel_consolidado_none.py` | Edge cases de exportação |
| `test_integracao.py` | Testes de integração entre módulos |
| `test_dq_staging.py` | Validações de qualidade de dados |

---

## Estrutura do Projeto

<details>
<summary><strong>Expandir estrutura completa</strong></summary>

```
plataforma-conta-grafica/
│
├── main.py                              # Entry point
├── start.py                             # Bootstrap Docker
├── docker-compose.yml                   # 5 serviços
├── init.sql                             # Inicialização do banco
├── requirements.txt                     # Dependências
├── pytest.ini                           # Configuração do pytest
├── COMANDOS.md                          # Atalhos e comandos úteis
│
├── Src/
│   ├── main_dashboard.py                # PlataformaFinanceira (janela principal)
│   │
│   ├── Views/
│   │   ├── tela_pmpv.py                 # TelaPMPV
│   │   ├── tela_concilia.py             # TelaConciliador
│   │   ├── tela_ret.py                  # TelaRET
│   │   ├── tela_auditoria.py            # TelaAuditoria
│   │   ├── tela_cgf.py                  # TelaCGF
│   │   ├── tela_rpv.py                  # TelaRPV
│   │   ├── tela_sr.py                   # TelaSR
│   │   └── tela_scg.py                  # TelaSCG
│   │
│   ├── Services/
│   │   ├── servicos_pmpv.py             # ExcelPMPV
│   │   ├── servicos_concilia.py         # RegrasConcilia
│   │   ├── servicos_ret.py              # RegrasRET
│   │   ├── servicos_auditoria.py        # RegrasAuditoria
│   │   ├── servicos_cgf.py              # ServicosCGF
│   │   ├── servicos_rpv.py              # ServicosRPV
│   │   ├── servicos_sr.py               # ServicosSR
│   │   ├── servicos_scg.py              # ServicosSCG
│   │   ├── servicos_consolidacao.py     # ServicosConsolidacao
│   │   ├── excel_concilia.py            # ExcelConcilia
│   │   ├── excel_auditoria.py           # ExcelAuditoria
│   │   └── excel_ret.py                 # ExcelRET
│   │
│   ├── Database/
│   │   └── database.py                  # DatabasePMPV (908 linhas, 12 tabelas)
│   │
│   ├── application/
│   │   └── use_cases/
│   │       └── pmpv_use_cases.py        # PMPVUseCases
│   │
│   ├── domain/
│   │   └── ports/
│   │       └── repositories.py          # Interfaces (ConsolidacaoRepository)
│   │
│   ├── infrastructure/
│   │   ├── exporters/
│   │   │   ├── excel_consolidado.py     # ExcelConsolidado (Módulo 9)
│   │   │   └── excel_handler_pmpv.py    # Handler PMPV
│   │   ├── ocr/
│   │   │   ├── ocr_pdf.py              # OCR com Tesseract
│   │   │   └── gemini_pdf.py           # OCR com Google Gemini
│   │   └── repositories/
│   │       └── sqlite_repositories.py   # Implementação SQLite
│   │
│   ├── common/
│   │   ├── periodos.py                  # Normalização de períodos
│   │   ├── excel_final_destino.py       # Modal de destino Excel
│   │   └── formatting.py               # Formatação BRL
│   │
│   ├── config/
│   │   └── ui_theme.py                  # Tema CustomTkinter
│   │
│   └── assets/
│       ├── icone.ico                    # Ícone da aplicação
│       ├── icons8-cash-94.ico           # Ícone alternativo
│       └── icons8-cash-94.png           # Logo do menu lateral
│
├── backend/
│   ├── airflow/
│   │   ├── Dockerfile
│   │   └── dags/                        # 6 DAGs
│   │
│   ├── etl/
│   │   ├── pipeline.py                  # Pipeline principal
│   │   ├── extractors/                  # Excel, PDF, XML
│   │   ├── transformers/                # PMPV, Auditoria, CGF, Concilia, RET
│   │   └── loaders/                     # PostgreSQL, SQLite
│   │
│   ├── data_quality/
│   │   ├── checks.py                    # Motor de validação
│   │   ├── dq_config.yaml               # Configuração de regras
│   │   └── run_checks.py               # Runner
│   │
│   ├── monitoring/
│   │   ├── anomaly_detector.py          # 5 tipos de anomalia
│   │   ├── alerter.py                   # Envio de alertas
│   │   └── email_template.html          # Template de e-mail
│   │
│   ├── reporting/
│   │   └── export_excel.py              # Geração de relatórios
│   │
│   ├── warehouse/
│   │   └── setup_warehouse.py           # Setup do DW
│   │
│   └── migrations/
│       └── migrate_sqlite_to_pg.py      # Migração SQLite → Postgres
│
└── tests/
    ├── test_database.py
    ├── test_servicos_consolidacao.py
    ├── test_servicos_cgf.py
    ├── test_pmpv_use_cases.py
    ├── test_regras_pmpv.py
    ├── test_excel_handler.py
    ├── test_excel_final_flow.py
    ├── test_excel_consolidado_none.py
    ├── test_integracao.py
    └── test_dq_staging.py
```

</details>

---

## Troubleshooting

<details>
<summary><strong>Excel final mistura períodos</strong></summary>

1. Verifique se o período foi informado corretamente no modal de cada módulo
2. Reutilize a mesma sessão de Excel no modal de destino
3. Confirme os registros na tabela `excel_final_execucoes`
4. O sistema normaliza períodos automaticamente (`Dez/25` → `Dez/2025`)

</details>

<details>
<summary><strong>Arquivo Excel não atualiza</strong></summary>

1. Feche o arquivo no Microsoft Excel antes de gerar novamente
2. Tente gerar para um novo caminho temporário
3. Verifique permissões de escrita na pasta de destino

</details>

<details>
<summary><strong>RET não aparece no consolidado</strong></summary>

1. Confirme que o RET foi processado e salvo para o período correto
2. Verifique se usou o botão **"Adicionar ao Excel Final (Módulo 9)"** no módulo RET
3. Consulte a tabela `ret_itens` no banco para confirmar a persistência

</details>

<details>
<summary><strong>Docker não sobe</strong></summary>

1. Verifique se o Docker Desktop está rodando
2. Libere as portas 5432 e 8080
3. Execute `docker-compose down -v` e tente novamente
4. Consulte `COMANDOS.md` para mais opções de troubleshooting

</details>

---

## Contribuição

1. Crie uma branch a partir de `main`:
   ```powershell
   git checkout -b feat/minha-feature
   ```
2. Implemente as alterações com testes
3. Execute a suite de testes:
   ```powershell
   python -m pytest
   ```
4. Faça commits semânticos em português:
   ```
   feat(banco): adicionar validação de período duplicado
   fix(servicos): corrigir cálculo de RPV quando CGF é zero
   test(consolidacao): cobrir cenário de exclusão em cascata
   ```
5. Abra um Pull Request com contexto funcional e técnico

---

<div align="center">

Desenvolvido para **ARPE** — Agência de Regulação de Pernambuco

</div>
