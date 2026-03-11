# Plataforma Conta Grafica (SCG)

Aplicacao desktop em Python para calculo e consolidacao financeira dos modulos PMPV, CGR, CGF, RET, RP, RPV e SCG.

## Visao Geral

- Interface desktop com `CustomTkinter`.
- Persistencia local em `SQLite`.
- Processamento de planilhas com `pandas` e `openpyxl`.
- OCR de PDF com `pdfplumber` e `pytesseract` (opcional).
- Testes com `pytest`.

## Arquitetura

O projeto esta organizado por camadas, com foco em separacao de responsabilidades:

```text
plataforma-conta-grafica/
├── Src/
│   ├── application/
│   │   └── use_cases/
│   │       └── pmpv_use_cases.py
│   ├── domain/
│   │   └── ports/
│   │       └── repositories.py
│   ├── infrastructure/
│   │   ├── repositories/
│   │   │   └── sqlite_repositories.py
│   │   └── exporters/
│   │       └── excel_handler_pmpv.py
│   ├── Database/
│   │   └── database.py
│   ├── Services/
│   │   ├── servicos_consolidacao.py
│   │   ├── servicos_pmpv.py
│   │   └── ...
│   ├── Views/
│   │   ├── tela_pmpv.py
│   │   ├── tela_scg.py
│   │   └── ...
│   ├── infra/
│   │   └── ocr_pdf.py
│   └── main_dashboard.py
├── tests/
│   ├── test_database.py
│   ├── test_excel_handler.py
│   ├── test_integracao.py
│   ├── test_servicos_consolidacao.py
│   └── test_pmpv_use_cases.py
├── main.py
├── requirements.txt
├── pytest.ini
└── README.md
```

## Regras de Negocio Principais

- `RPV = CGR - CGF`
- `SCG = RPV + RET + RP`

## Requisitos

- Python 3.10+
- Windows (principal ambiente alvo atual)

## Instalacao

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Execucao

```bash
python main.py
```

## Testes

```bash
pytest
```

Se `pytest` nao estiver instalado no ambiente:

```bash
pip install pytest
```

## Seguranca

Checklist rapido para publicacao (GitHub/LinkedIn):

- Nao ha chaves de API, tokens ou segredos hardcoded no repositorio.
- Arquivos de banco local (`*.db`, `*.sqlite`, `*.sqlite3`) estao ignorados no `.gitignore`.
- O OCR usa caminho de Tesseract configuravel por variavel de ambiente `TESSERACT_CMD` e caminhos padrao do sistema, sem caminho pessoal fixo.
- O projeto nao depende de servicos externos sensiveis para rodar.

Recomendacoes adicionais:

- Nunca commitar bancos reais com dados de producao.
- Evitar publicar planilhas com dados sensiveis em exemplos.
- Se no futuro houver API externa, usar variaveis de ambiente (`.env`) e rotacao de chaves.

## Roadmap Tecnico

- Melhorar cobertura de testes de interface e fluxos end-to-end.
- Adicionar CI para rodar lint e testes automaticamente.
- Evoluir contratos de `domain/ports` para todos os modulos.
- Padronizar tratamento de erros e telemetria de falhas.

## Licenca

Definir licenca do projeto (ex.: MIT) antes da publicacao publica.
