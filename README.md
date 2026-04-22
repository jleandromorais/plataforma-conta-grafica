<div align="center">
  <img src="Src/assets/icons8-cash-94.png" alt="Plataforma Conta Gráfica" width="90" />

  <h1>Plataforma Conta Gráfica</h1>

  <p>
    <strong>Sistema integrado de gestão financeira para apuração de Conta Gráfica<br/>no mercado regulado de gás canalizado</strong>
  </p>

  <p><em>Desenvolvido para a ARPE — Agência de Regulação de Pernambuco</em></p>

  <br/>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
    <img src="https://img.shields.io/badge/UI-CustomTkinter-2B2B2B?style=for-the-badge&logo=python&logoColor=white" alt="CustomTkinter"/>
    <img src="https://img.shields.io/badge/SQLite-Local-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite"/>
    <img src="https://img.shields.io/badge/PostgreSQL-DataWarehouse-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
    <img src="https://img.shields.io/badge/Airflow-2.9.0-017CEE?style=for-the-badge&logo=apacheairflow&logoColor=white" alt="Airflow"/>
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
    <img src="https://img.shields.io/badge/pytest-11_arquivos-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" alt="pytest"/>
  </p>

  <br/>

  <p>
    <a href="#-visão-geral">Visão Geral</a> &nbsp;•&nbsp;
    <a href="#-módulos">Módulos</a> &nbsp;•&nbsp;
    <a href="#-arquitetura">Arquitetura</a> &nbsp;•&nbsp;
    <a href="#-instalação">Instalação</a> &nbsp;•&nbsp;
    <a href="#-backend">Backend</a> &nbsp;•&nbsp;
    <a href="#-testes">Testes</a> &nbsp;•&nbsp;
    <a href="#-troubleshooting">Troubleshooting</a>
  </p>
</div>

---

## 📋 Visão Geral

Aplicação **desktop Windows** para apuração completa de Conta Gráfica do mercado regulado de gás, composta por **8 módulos especializados** que calculam e consolidam os componentes financeiros — PMPV, CGR, CGF, RET, RPV, SR e SCG — em um único relatório Excel unificado.

O repositório também inclui uma **stack de backend** com Apache Airflow e PostgreSQL para automação de ETL, validação de qualidade de dados e geração de relatórios agendados.

<br/>

<div align="center">

| 📁 Arquivos Python | 🖥️ Módulos UI | ⚙️ Serviços | 🗄️ Tabelas | 🧪 Testes | 🔄 DAGs | 📦 Componentes ETL |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **84+** | **8** | **12** | **12** | **11** | **6** | **10** |

</div>

---

## 🧩 Módulos

A aplicação é composta por 9 módulos que operam em sequência até a geração do relatório final:

<br/>

<table>
  <thead>
    <tr>
      <th align="center">#</th>
      <th>Módulo</th>
      <th>Fórmula / Lógica</th>
      <th>Entrada</th>
      <th>Saída</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td align="center"><strong>1</strong></td>
      <td>📊 <strong>PMPV</strong></td>
      <td>Preço Médio Ponderado por Volume (trimestral)</td>
      <td>Planilhas Excel</td>
      <td>PMPV em R$/m³ por período</td>
    </tr>
    <tr>
      <td align="center"><strong>2</strong></td>
      <td>🔀 <strong>Conciliação RP</strong></td>
      <td>Consolidação receitas × despesas</td>
      <td>PDFs (com OCR)</td>
      <td>Itens conciliados</td>
    </tr>
    <tr>
      <td align="center"><strong>3</strong></td>
      <td>🚚 <strong>RET</strong></td>
      <td>Recuperação de Encargos de Transporte</td>
      <td>Pasta de PDFs</td>
      <td>Classificação EAT / EC / TOP / Penalidades</td>
    </tr>
    <tr>
      <td align="center"><strong>4</strong></td>
      <td>🔍 <strong>Auditoria XML</strong></td>
      <td><code>CGR = (Σ valor − Σ ICMS) × (1 − PIS − COFINS)</code></td>
      <td>XML NF-e / CT-e</td>
      <td>CGR líquido por empresa</td>
    </tr>
    <tr>
      <td align="center"><strong>5</strong></td>
      <td>📦 <strong>CGF</strong></td>
      <td>Volume Faturado − Cancelados − Devoluções − Consumo próprio</td>
      <td>Excel / CSV</td>
      <td>Volume final faturado</td>
    </tr>
    <tr>
      <td align="center"><strong>6</strong></td>
      <td>⚖️ <strong>RPV</strong></td>
      <td><code>RPV = CGR − CGF</code></td>
      <td>Banco de dados</td>
      <td>Saldo RPV</td>
    </tr>
    <tr>
      <td align="center"><strong>7</strong></td>
      <td>💹 <strong>SR</strong></td>
      <td><code>SR = (VP − VF) × PR</code></td>
      <td>Sessões PMPV</td>
      <td>Receita Suplementar</td>
    </tr>
    <tr>
      <td align="center"><strong>8</strong></td>
      <td>📈 <strong>SCG</strong></td>
      <td><code>SCG = RPV + RET + RP</code></td>
      <td>Todos os módulos</td>
      <td>Saldo Conta Gráfica</td>
    </tr>
    <tr>
      <td align="center"><strong>9</strong></td>
      <td>📤 <strong>Excel Final</strong></td>
      <td>Consolidação de todas as etapas</td>
      <td>Banco de dados</td>
      <td>Arquivo <code>.xlsx</code> unificado</td>
    </tr>
  </tbody>
</table>

### Fluxo de operação

```
   ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌────────────┐
   │  PMPV   │    │ Auditoria│    │   CGF   │    │    RET     │
   │ (Excel) │    │  (XML)   │    │(Excel)  │    │  (PDFs)    │
   └────┬────┘    └────┬─────┘    └────┬────┘    └─────┬──────┘
        │              │               │                │
        │              └───────┬───────┘                │
        │                      │                        │
        │               ┌──────▼──────┐                 │
        │               │ RPV=CGR−CGF │                 │
        │               └──────┬──────┘                 │
        │                      │                        │
   ┌────▼────┐          ┌──────▼──────┐         ┌──────▼──────┐
   │   SR    │          │     SCG     │         │  Concilia   │
   │(VP−VF)×PR│         │ RPV+RET+RP  │         │    (RP)     │
   └────┬────┘          └──────┬──────┘         └──────┬──────┘
        │                      │                        │
        └──────────────────────┼────────────────────────┘
                               │
                      ┌────────▼────────┐
                      │   Excel Final   │
                      │   (Módulo 9)    │
                      └─────────────────┘
```

> **Passo a passo:** abra o app → processe cada módulo para o período desejado (ex: `Dez/2025`) → clique em **"Adicionar ao Excel Final (Módulo 9)"** em cada tela → gere o relatório consolidado no Módulo 9.

---

## 🏗️ Arquitetura

O projeto segue **Clean Architecture** com quatro camadas bem definidas:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Views (CustomTkinter)                      │
│      PMPV · Auditoria · CGF · RET · Concilia · RPV · SR · SCG  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                           Services                              │
│          Regras de negócio, cálculos, formatação BRL            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Infrastructure / Database                    │
│      SQLite (local) · Exportadores Excel · OCR / Gemini API     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                     Backend (opcional)                          │
│        Airflow DAGs → ETL → PostgreSQL → Relatórios             │
└─────────────────────────────────────────────────────────────────┘
```

### Estrutura de diretórios

```
plataforma-conta-grafica/
│
├── main.py                          # Entry point da aplicação desktop
├── start.py                         # Bootstrap automático da stack Docker
├── docker-compose.yml               # 5 serviços orquestrados
├── requirements.txt                 # Dependências Python
│
├── Src/                             # Aplicação desktop
│   ├── main_dashboard.py            # Janela principal (PlataformaFinanceira)
│   ├── Views/                       # 8 telas CustomTkinter
│   ├── Services/                    # Regras de negócio por módulo
│   ├── Database/                    # Persistência SQLite (DatabasePMPV)
│   ├── application/                 # Casos de uso (Clean Architecture)
│   ├── domain/                      # Contratos e interfaces (ports)
│   ├── infrastructure/              # Exportadores Excel, OCR, repositórios
│   ├── common/                      # Normalização de período, utilitários de UI
│   ├── config/                      # Tema e configurações visuais
│   └── assets/                      # Ícones da aplicação
│
├── backend/                         # Stack de dados empresarial
│   ├── airflow/                     # Dockerfile + 6 DAGs de orquestração
│   ├── etl/                         # Extractors, Transformers, Loaders
│   ├── data_quality/                # Validações SQL + config YAML
│   ├── monitoring/                  # Detector de anomalias + alertas por e-mail
│   ├── reporting/                   # Geração agendada de relatórios Excel
│   ├── warehouse/                   # Setup do data warehouse PostgreSQL
│   └── migrations/                  # Migração SQLite → PostgreSQL
│
└── tests/                           # Suite de testes automatizados (pytest)
```

<details>
<summary><strong>Ver estrutura completa de arquivos</strong></summary>

```
plataforma-conta-grafica/
├── Src/
│   ├── main_dashboard.py
│   ├── Views/
│   │   ├── tela_pmpv.py
│   │   ├── tela_concilia.py
│   │   ├── tela_ret.py
│   │   ├── tela_auditoria.py
│   │   ├── tela_cgf.py
│   │   ├── tela_rpv.py
│   │   ├── tela_sr.py
│   │   └── tela_scg.py
│   ├── Services/
│   │   ├── servicos_pmpv.py
│   │   ├── servicos_concilia.py
│   │   ├── servicos_ret.py
│   │   ├── servicos_auditoria.py
│   │   ├── servicos_cgf.py
│   │   ├── servicos_rpv.py
│   │   ├── servicos_sr.py
│   │   ├── servicos_scg.py
│   │   ├── servicos_consolidacao.py
│   │   ├── excel_concilia.py
│   │   ├── excel_auditoria.py
│   │   └── excel_ret.py
│   ├── Database/
│   │   └── database.py              # DatabasePMPV — 12 tabelas, 908 linhas
│   ├── application/use_cases/
│   │   └── pmpv_use_cases.py
│   ├── domain/ports/
│   │   └── repositories.py          # Interfaces (ConsolidacaoRepository)
│   ├── infrastructure/
│   │   ├── exporters/
│   │   │   ├── excel_consolidado.py # ExcelConsolidado (Módulo 9)
│   │   │   └── excel_handler_pmpv.py
│   │   ├── ocr/
│   │   │   ├── ocr_pdf.py           # OCR com Tesseract
│   │   │   └── gemini_pdf.py        # OCR com Google Gemini
│   │   └── repositories/
│   │       └── sqlite_repositories.py
│   ├── common/
│   │   ├── periodos.py              # Normalização de períodos
│   │   ├── excel_final_destino.py   # Modal de destino Excel
│   │   └── formatting.py           # Formatação BRL
│   ├── config/
│   │   └── ui_theme.py
│   └── assets/
│       ├── icone.ico
│       └── icons8-cash-94.png
│
├── backend/
│   ├── airflow/
│   │   ├── Dockerfile
│   │   └── dags/
│   │       ├── dag_auditoria.py
│   │       ├── dag_ret.py
│   │       ├── dag_consolidacao.py
│   │       ├── dag_data_quality.py
│   │       ├── dag_monitoramento_alertas.py
│   │       └── dag_export_excel.py
│   ├── etl/
│   │   ├── pipeline.py
│   │   ├── extractors/              # excel_extractor, pdf_extractor, xml_extractor
│   │   ├── transformers/            # pmpv, auditoria, cgf, concilia, ret
│   │   └── loaders/                 # postgres_loader, sqlite_loader
│   ├── data_quality/
│   │   ├── checks.py
│   │   ├── dq_config.yaml
│   │   └── run_checks.py
│   ├── monitoring/
│   │   ├── anomaly_detector.py
│   │   ├── alerter.py
│   │   └── email_template.html
│   ├── reporting/
│   │   └── export_excel.py
│   ├── warehouse/
│   │   └── setup_warehouse.py
│   └── migrations/
│       └── migrate_sqlite_to_pg.py
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

## 🚀 Instalação

### Pré-requisitos

| Requisito | Versão | Obrigatório |
|-----------|--------|:-----------:|
| Windows | 10 / 11 | ✅ |
| Python | 3.10+ | ✅ |
| PowerShell | 5.1+ | ✅ |
| Docker Desktop | 4.0+ | ⬜ (apenas para backend) |

### Configuração do ambiente

```powershell
# 1. Clonar o repositório
git clone https://github.com/jleandromorais/plataforma-conta-grafica.git
cd plataforma-conta-grafica

# 2. Criar e ativar ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependências
pip install -r requirements.txt

# 4. (Opcional) Gerar executável .exe
pyinstaller --noconfirm --clean --windowed --name PlataformaFinanceira main.py
# → dist/PlataformaFinanceira/PlataformaFinanceira.exe
```

### Executar

```powershell
# Aplicação desktop (standalone, sem Docker)
python main.py

# Backend com Docker (Airflow + PostgreSQL)
python start.py        # inicialização automática
# ou manualmente:
docker-compose up -d
```

| Serviço | Endereço | Credenciais |
|---------|----------|-------------|
| Airflow Web UI | http://localhost:8080 | `airflow` / `airflow` |
| PostgreSQL | `localhost:5432` | `postgres` / `admin` |

---

## 🗄️ Banco de Dados

A persistência local usa **SQLite** (`pmpv_data.db`) com **12 tabelas**:

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

#### Normalização automática de períodos

O sistema converte variantes de formato automaticamente, evitando fragmentação de dados:

```
Dez/25   →   Dez/2025
DEZ/25   →   Dez/2025
12/25    →   Dez/2025
```

---

## ⚙️ Backend

A stack de backend é **opcional** e fornece automação, qualidade de dados e relatórios agendados.

### Serviços Docker

| Serviço | Imagem | Porta | Função |
|---------|--------|:-----:|--------|
| `postgres` | `postgres:13` | — | Metadados do Airflow |
| `postgres-data` | `postgres:13` | `5432` | Data warehouse da aplicação |
| `airflow-webserver` | Custom | `8080` | Interface web |
| `airflow-scheduler` | Custom | — | Agendador de DAGs |
| `airflow-init` | Custom | — | Inicialização e migração |

### DAGs disponíveis

| DAG | Função | Frequência |
|-----|--------|:---------:|
| `pipeline_auditoria_xml` | ETL de XMLs de auditoria | Diária |
| `pipeline_ret_pdf` | ETL de PDFs do RET | Diária |
| `pipeline_consolidacao` | Reconsolidação de dados | Diária |
| `dag_data_quality_diaria` | Validação de qualidade | Diária |
| `dag_monitoramento_alertas` | Detecção de anomalias + alertas | Diária |
| `dag_export_excel` | Geração de relatório Excel | Agendada |

### Pipeline ETL

```
Extractors              Transformers                Loaders
──────────────          ─────────────────           ─────────────────
excel_extractor   →     pmpv_transform        →     postgres_loader
pdf_extractor     →     auditoria_transform   →     sqlite_loader
xml_extractor     →     cgf_transform
                        concilia_transform
                        ret_transform
```

### Data Quality e Monitoramento

Validações configuráveis via `dq_config.yaml`:

- **SQL checks** — consultas que retornam linhas indicam falha
- **Threshold checks** — métricas escalares comparadas a limites configuráveis

O `AnomalyDetector` verifica **5 tipos de anomalia** automaticamente:

1. Falhas de qualidade nas últimas 24h
2. Atraso de importação superior a 3 dias
3. Volume CGF zerado ou nulo
4. Períodos duplicados
5. Taxa de rejeição acima do limite

> Alertas são disparados por e-mail com templates HTML via SMTP configurado em `backend/.env`.

---

## 🧪 Testes

```powershell
# Suite completa
python -m pytest

# Com relatório de cobertura
python -m pytest --cov=Src --cov-report=html

# Módulos específicos
python -m pytest tests/test_database.py -v
python -m pytest tests/test_excel_final_flow.py tests/test_excel_consolidado_none.py -v
python -m pytest tests/test_servicos_consolidacao.py -v

# Por marcador
python -m pytest -m unit
python -m pytest -m integration
```

| Arquivo de Teste | Cobertura |
|------------------|-----------|
| `test_database.py` | Persistência SQLite, normalização de períodos, exclusão em cascata |
| `test_servicos_consolidacao.py` | Regras de consolidação SCG |
| `test_servicos_cgf.py` | Cálculos de volume CGF |
| `test_pmpv_use_cases.py` | Casos de uso PMPV |
| `test_regras_pmpv.py` | Regras de negócio PMPV |
| `test_excel_handler.py` | Leitura e escrita de Excel |
| `test_excel_final_flow.py` | Fluxo completo do Módulo 9 |
| `test_excel_consolidado_none.py` | Edge cases de exportação |
| `test_integracao.py` | Integração entre módulos |
| `test_dq_staging.py` | Validações de qualidade de dados |

---

## 🔧 Troubleshooting

<details>
<summary><strong>Excel final mistura períodos</strong></summary>

1. Verifique se o período foi informado corretamente no modal de cada módulo
2. Reutilize a mesma sessão de Excel no modal de destino
3. Confirme os registros na tabela `excel_final_execucoes`
4. O sistema normaliza períodos automaticamente — certifique-se de não criar sessões duplicadas com formatos diferentes

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
2. Verifique se o botão **"Adicionar ao Excel Final (Módulo 9)"** foi utilizado no módulo RET
3. Consulte a tabela `ret_itens` no banco para confirmar a persistência

</details>

<details>
<summary><strong>Docker não sobe</strong></summary>

1. Verifique se o Docker Desktop está rodando
2. Libere as portas `5432` e `8080`
3. Execute `docker-compose down -v` e tente novamente
4. Consulte `COMANDOS.md` para mais receitas de troubleshooting

</details>

---

## 🤝 Contribuição

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

  <br/>

  Desenvolvido para &nbsp;<strong>ARPE</strong> — Agência de Regulação de Pernambuco

  <br/><br/>

  ![Python](https://img.shields.io/badge/feito_com-Python-3776AB?style=flat-square&logo=python&logoColor=white)
  &nbsp;
  ![Windows](https://img.shields.io/badge/plataforma-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)

</div>
