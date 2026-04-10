# Plataforma Conta Grafica

Sistema desktop em Python para apuracao de Conta Grafica, com modulos fiscais/operacionais e geracao de Excel consolidado (Modulo 9). O repositorio tambem inclui stack de backend (Airflow + PostgreSQL) para rotinas de dados e relatorios.

## O que este projeto faz

- Calcula PMPV por sessao e periodo.
- Processa Auditoria XML (NF-e/CT-e) para apuracao de CGR.
- Processa RET e Conciliacao RP a partir de PDFs.
- Calcula CGF, RPV, SR e SCG.
- Consolida os resultados em um unico Excel final (Modulo 9), com controle de sessoes e execucoes.

## Arquitetura (visao rapida)

```text
plataforma-conta-grafica/
|- Src/
|  |- application/        # Casos de uso
|  |- domain/             # Contratos e modelos
|  |- Services/           # Regras de negocio por modulo
|  |- Views/              # Telas (customtkinter)
|  |- infrastructure/     # Exportadores, OCR, integracoes
|  |- Database/           # Persistencia SQLite
|  |- common/             # Helpers de fluxo e UI
|  `- main_dashboard.py   # Janela principal
|- backend/               # Airflow, ETL, DQ, reporting
|- tests/                 # Testes automatizados
|- main.py                # Entry point principal da UI
|- start.py               # Bootstrap da stack Docker
|- docker-compose.yml
|- requirements.txt
`- COMANDOS.md
```

## Modulos da UI

- PMPV
- Conciliacao RP
- RET
- Auditoria XML
- CGF
- RPV
- SR
- SCG
- Excel Final Consolidado (Modulo 9)

## Pre-requisitos

- Windows (ambiente principal de uso)
- Python 3.10+
- PowerShell
- Docker Desktop (opcional, para backend/Airflow)

## Instalacao local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dependencias principais em uso no projeto:

- pandas
- openpyxl
- sqlalchemy
- psycopg2-binary
- python-dotenv
- pytesseract
- PyYAML
- google-genai

## Como executar

### 1) Aplicacao desktop (recomendado)

```powershell
python main.py
```

Alternativa direta:

```powershell
python Src/main_dashboard.py
```

### 2) Stack backend com Docker (opcional)

```powershell
python start.py
```

ou

```powershell
docker-compose up -d
```

Airflow Web UI:

- URL: http://localhost:8080
- Usuario: airflow
- Senha: airflow

## Fluxo recomendado de operacao

1. Execute os modulos por periodo (ex.: `Dez/2025`).
2. Em cada modulo, use o botao `Adicionar ao Excel Final (Modulo 9)`.
3. Escolha/reutilize a sessao de Excel final no modal CTk.
4. Gere o consolidado final por periodo para evitar mistura de dados.

## Modulo 9 (Excel Final) - Regras importantes

O fluxo atual foi padronizado para evitar mistura de sessoes:

- A selecao de destino do Excel final ocorre em modal CTk (`Src/common/excel_final_destino.py`).
- Cada inclusao registra execucao por chave logica: `nome_sessao + periodo + etapa`.
- A exportacao consolidada usa periodo explicito (normalizado), evitando `periodo=None` por engano nas telas principais.

Arquivos relevantes do fluxo:

- `Src/common/excel_final_destino.py`
- `Src/infrastructure/exporters/excel_consolidado.py`
- `Src/Database/database.py`

## Banco de dados

Persistencia principal local:

- `pmpv_data.db` (SQLite)

Tabelas importantes para o Modulo 9:

- `excel_final_sessoes`
- `excel_final_execucoes`
- tabelas de dados por modulo (`ret_itens`, `auditoria_itens`, `concilia_itens`, `cgf_resumo`, `sr_resultados`, `consolidacao`)

## Testes

Rodar suite completa:

```powershell
python -m pytest
```

Rodar testes focados do fluxo Excel Final:

```powershell
python -m pytest tests/test_excel_final_flow.py tests/test_excel_consolidado_none.py -q
```

## Comandos uteis

Veja `COMANDOS.md` para atalhos de:

- subida e operacao do Docker
- logs do Airflow/PostgreSQL
- troubleshooting
- testes especificos

## Troubleshooting

### Excel final mistura periodos

- Garanta que o periodo foi informado no modal de periodo do modulo.
- Reuse a sessao correta do Excel final no modal de destino.
- Verifique registros em `excel_final_execucoes`.

### Arquivo Excel nao atualiza

- Feche o arquivo no Excel e tente novamente.
- Gere para um novo caminho temporario e valide.

### RET nao aparece no consolidado

- Confirme que o RET foi processado e salvo no periodo correto.
- Confirme que foi usado `Adicionar ao Excel Final (Modulo 9)` no RET.

## Contribuicao

1. Crie branch de feature/fix.
2. Rode testes antes do commit.
3. Faça commits semanticos curtos e objetivos.
4. Abra PR com contexto funcional e tecnico.

## Licenca

Licenca ainda nao definida no repositorio.
