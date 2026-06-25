# Arquitetura — GraphAccount Pro

Este documento descreve a arquitetura do sistema e as decisões que a sustentam.
Leia antes de adicionar um novo módulo.

## Visão geral: Clean Architecture

O sistema segue **Clean Architecture** (também chamada hexagonal / ports & adapters).
A regra de ouro é a **inversão de dependência**: o núcleo (domínio) não depende de
detalhes externos (banco, UI, arquivos). Quem depende de quem:

```
        ┌─────────────────────────────────────────────┐
        │                  Views (UI)                  │  customtkinter
        │            Src/Views/tela_*.py               │
        └───────────────────────┬─────────────────────┘
                                 │ chama
        ┌───────────────────────▼─────────────────────┐
        │        Services / Use Cases (aplicação)      │  orquestração
        │   Src/Services/*  ·  Src/application/*        │
        └───────────────────────┬─────────────────────┘
                                 │ depende de (Protocol)
        ┌───────────────────────▼─────────────────────┐
        │           Ports (domínio) — contratos        │  interfaces
        │        Src/domain/ports/repositories.py      │
        └───────────────────────▲─────────────────────┘
                                 │ implementa
        ┌───────────────────────┴─────────────────────┐
        │        Repositories (infraestrutura)         │  SQLite
        │  Src/infrastructure/repositories/sqlite_*    │
        └───────────────────────┬─────────────────────┘
                                 │ usa
        ┌───────────────────────▼─────────────────────┐
        │          DatabasePMPV (acesso SQLite)        │
        │            Src/Database/database.py          │
        └─────────────────────────────────────────────┘
```

## Camadas

- **domain/ports** — Interfaces (`Protocol`) que definem *o quê* a aplicação precisa
  de um repositório, sem dizer *como*. Ex.: `PMPVRepository`, `ConsolidacaoRepository`,
  `SRRepository`, `PRRepository`.
- **application / Services** — Orquestram fluxos e contêm as **regras de negócio**
  (cálculos puros, estáticos e testáveis). Recebem um repositório por **injeção de
  dependência** (parâmetro `repo=`), com um default concreto para uso real.
- **infrastructure/repositories** — Implementações concretas dos ports usando SQLite.
  São adaptadores finos sobre `DatabasePMPV`.
- **Database** — `DatabasePMPV`: acesso de baixo nível ao SQLite.
- **Views** — UI (customtkinter). Não devem conter regra de negócio nem SQL.

## Regra obrigatória para NOVOS módulos

**Todo módulo que acessa dados DEVE seguir o padrão de Clean Architecture.**
Nenhum Service ou View pode instanciar `DatabasePMPV()` diretamente. Em vez disso:

1. Defina um `Protocol` em `Src/domain/ports/repositories.py` com os métodos que precisa.
2. Implemente esse Protocol em `Src/infrastructure/repositories/sqlite_repositories.py`.
3. No Service, receba o repositório por injeção:
   ```python
   def __init__(self, repo: MeuRepository | None = None):
       self._repo = repo or SqliteMeuRepository()
   ```
4. Teste o Service com um mock/fake do Protocol (sem tocar no banco real).

Benefícios: testabilidade (mocks), troca de infraestrutura sem mexer no domínio e
limites claros entre as camadas.

## Padrões transversais

- **Logging**: configurado em `Src/config/logging_config.py` (arquivo `logs/app.log`
  rotativo). Em blocos `except`, use `logger.exception(...)` — nunca `print`.
- **Tema/Design System**: `Src/config/ui_theme.py` centraliza cores, tipografia e
  espaçamento. As Views devem importar daqui, não escrever cores "soltas".
- **Banco**: `DatabasePMPV` é um context manager (`with DatabasePMPV() as db:`),
  usa WAL e tem `backup()`. Nomes de tabela em SQL são validados por allow-list.

## Fonte única de verdade (cálculos)

**Toda regra de cálculo da conta gráfica vive em `Src/Services/*`.** É a única fonte
oficial, consumida tanto pelo app desktop (Views) quanto pela automação (`pipeline.py`).
Nenhum outro módulo deve reimplementar fórmula de CGR/RET/CGF/RP/PMPV/SCG — se precisar
do cálculo em outro lugar, importe o Service correspondente.

O antigo `backend/` (pipeline Airflow + Postgres) foi **arquivado** em `_arquivado/backend/`
porque mantinha uma cópia paralela desses cálculos que já havia divergido da oficial
(detalhes em `_arquivado/README.md`). A automação suportada é `pipeline.py` + Windows
Task Scheduler + SQLite.

## Dívida técnica conhecida

- `DatabasePMPV` ainda é uma classe grande (conhece todas as tabelas). O caminho de
  evolução é dividi-la por agregado, mas os repositórios já isolam as Views/Services
  desse detalhe — a migração pode ser gradual e sem impacto nas camadas superiores.
- `commit` é feito por método no `DatabasePMPV`; transações compostas ainda não são
  totalmente controladas pelo chamador.
