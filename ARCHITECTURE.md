# Arquitetura — Plataforma Conta Gráfica ARPE (back-end)

Este documento descreve como o código de `Src/` está organizado e as regras que o mantêm assim.
Leia antes de criar um módulo novo. Atualizado em 13/11/2026.

## Visão geral: Clean Architecture

O sistema segue **Clean Architecture** (também chamada hexagonal, ou *ports & adapters*).
A regra de ouro é a **inversão de dependência**: as contas (o núcleo) não dependem de detalhes
externos, como banco, tela, arquivos ou HTTP. Quem depende de quem:

```
   Views (desktop)                         API (site)
   Src/Views/tela_*.py                     Src/api/ (routers, schemas)
   customtkinter                           FastAPI, usada pelo Front_end
          │                                     │
          └─────────────── chamam ──────────────┘
                              │
          ┌───────────────────▼────────────────────┐
          │   Use Cases + Services (aplicação)      │  fluxos e FÓRMULAS
          │   Src/application/use_cases/            │
          │   Src/Services/<etapa>/servicos_*.py    │
          │   Src/Services/comparacao/              │
          └───────────────────┬────────────────────┘
                              │ dependem só do contrato (Protocol)
          ┌───────────────────▼────────────────────┐
          │   Ports (domínio): contratos            │
          │   Src/domain/ports/repositories.py      │
          └───────────────────▲────────────────────┘
                              │ implementam
          ┌───────────────────┴────────────────────┐
          │   Infraestrutura (adaptadores)          │
          │   repositories/ (SQLite) · exporters/   │
          │   (Excel, Word) · ocr/ (PDF)            │
          └───────────────────┬────────────────────┘
                              │ usa
          ┌───────────────────▼────────────────────┐
          │   DatabasePMPV: acesso ao SQLite        │
          │   Src/Database/database.py              │
          └────────────────────────────────────────┘
```

As duas portas de entrada (o desktop e a API do site) usam **as mesmas** contas. É isso que
garante que o site, o `.exe` e o `pipeline.py` deem o mesmo resultado.

## Camadas e pastas

| Pasta | Camada | O que tem |
|---|---|---|
| `Src/api/` | Entrada (web) | `main.py` (app FastAPI), `routers/` (uma rota por módulo: pmpv, auditoria, cgf, ret, conciliacao, rpv, scg, sr, pr, pv, dashboard, relatorio_trimestral, nota_tecnica, excel_final, periodos, config, auth), `schemas/` (Pydantic, o formato de entrada e saída), `auth.py`, `deps.py`, `errors.py`, `erros_ciclo.py` (campo `erros` do Painel do Ciclo), `uploads.py`, `serve.py` (sobe o servidor) |
| `Src/Views/` | Entrada (desktop) | Telas customtkinter (`tela_*.py`, `dashboard_resumo.py`). Não devem ter regra de negócio nem SQL |
| `Src/main_dashboard.py` | Entrada (desktop) | Janela principal do app desktop |
| `Src/application/use_cases/` | Aplicação | Fluxos de várias etapas: `pmpv_use_cases.py`, `sr_use_cases.py` (carregar e propor o SR do trimestre), `dashboard_use_cases.py` |
| `Src/Services/tarifa/` | Aplicação | **Fórmulas da tarifa** (trimestres Nov–Jan, Fev–Abr…): `servicos_pmpv`, `servicos_pr`, `servicos_pr_automatico` (regrava PR e PV quando um módulo é salvo), `servicos_pv`, `servicos_margem`, `servicos_selic` |
| `Src/Services/auditoria/` | Aplicação | CGR: `servicos_auditoria` (regras fiscais de NF-e/CT-e), `servicos_auditoria_lote` (pasta inteira), `supridores` (cadastro e identificação dos supridores) |
| `Src/Services/cgf/` | Aplicação | `servicos_cgf`: volume faturado e CGF em R$ |
| `Src/Services/ret/` | Aplicação | `servicos_ret`, `servicos_ret_lote`: encargos de transporte |
| `Src/Services/rp/` | Aplicação | `servicos_concilia`, `servicos_concilia_lote`: RP (receitas e despesas de penalidade) |
| `Src/Services/apuracao/` | Aplicação | **Fórmulas da apuração** (trimestres civis): `servicos_rpv`, `servicos_scg`, `servicos_sr`, `servicos_consolidacao`, `servicos_periodos` |
| `Src/Services/comparacao/` | Aplicação | Comparadores da Auditoria com as planilhas oficiais (NT, modelo Alexandre, Apuração de Custos), `comparacao_registro.py` (escolhe o comparador pelo modelo da planilha), `diferencas_auditoria.py` e `explicador_diferencas.py` (onde e por que difere) |
| `Src/domain/ports/` | Domínio | Contratos (`Protocol`): `ConsolidacaoRepository`, `PMPVRepository`, `SRRepository`, `PRRepository` |
| `Src/infrastructure/repositories/` | Infraestrutura | `sqlite_repositories.py`: os contratos implementados sobre o SQLite |
| `Src/infrastructure/exporters/` | Infraestrutura | Arquivos gerados: Excel de cada módulo (`excel_auditoria.py`, `excel_concilia.py`, `excel_ret.py`), Excel Final (`excel_consolidado.py`, `excel_sheets/`, `excel_styles.py`), PMPV (`excel_handler_pmpv.py`), Nota Técnica em Word (`nota_tecnica.py`, `modelos/`), relatório do trimestre em Word (`relatorio_trimestral.py`) |
| `Src/infrastructure/ocr/` | Infraestrutura | Leitura de PDF: `ocr_pdf.py` (Tesseract) e `gemini_pdf.py` |
| `Src/Database/` | Infraestrutura | `database.py`: `DatabasePMPV`, o acesso de baixo nível ao SQLite |
| `Src/common/` | Transversal | Utilitários sem regra de negócio: `periodos.py` (normalização de "Out/2025", trimestres), `precisao.py` (arredondamento), `formatting.py`, `duplicatas.py`, `excel_salvar.py`, `app_paths.py`, `excel_final_destino.py` |
| `Src/config/` | Transversal | `logging_config.py` e `ui_theme.py` (tema do desktop) |
| `Src/assets/` | — | Ícones e splash do `.exe` |

Fora de `Src/`, na raiz: `main.py` (abre o desktop), `start.py`, `pipeline.py` + `notificador.py` +
`instalar_agendamento.py` (automação pelo Agendador do Windows), `Dockerfile` (API no Railway).
Esses ficam na raiz de propósito: o agendamento e o `.exe` apontam para eles ali.

## Regra obrigatória para NOVOS módulos

**Todo módulo que acessa dados deve passar por um repositório.** Nenhum Service, View ou rota
deve criar `DatabasePMPV()` direto. Em vez disso:

1. Defina um `Protocol` em `Src/domain/ports/repositories.py` com os métodos que o módulo precisa.
2. Implemente esse Protocol em `Src/infrastructure/repositories/sqlite_repositories.py`.
3. No Service ou Use Case, receba o repositório por injeção:
   ```python
   def __init__(self, repo: MeuRepository | None = None):
       self._repo = repo or SqliteMeuRepository()
   ```
4. Teste com um mock ou fake do Protocol, sem tocar no banco real.

Rotas novas da API seguem o mesmo caminho: `router → schema Pydantic → Use Case/Service → repositório`
(contrato em `docs/SPEC_BACKEND_FASTAPI.md`). A rota não faz conta: só traduz HTTP para chamada de Service.

Arquivos gerados (Excel, Word, PDF) vão em `infrastructure/exporters/`, não em `Services/`.
Service novo entra na pasta da etapa a que pertence (`tarifa/`, `auditoria/`, `cgf/`, `ret/`, `rp/`,
`apuracao/`, `comparacao/`); não deixe arquivo solto na raiz de `Services/`.

## Fonte única de verdade (cálculos)

**Toda regra de cálculo da conta gráfica vive em `Src/Services/`.** É a única fonte oficial, usada
pela API (site), pelo desktop (Views) e pela automação (`pipeline.py`). Nenhum outro módulo deve
reimplementar a fórmula de CGR, CGF, RET, RP, RPV, SCG, SR, PR, PV ou PMPV. Se precisar do cálculo
em outro lugar, importe o Service.

O antigo `backend/` (Airflow + Postgres) foi **arquivado** em `_arquivado/backend/` porque tinha uma
cópia paralela das contas que já havia divergido da oficial (detalhes em `_arquivado/README.md`).
Scripts de depuração antigos estão em `_arquivado/scripts_debug/`.

## Padrões transversais

- **Logging**: `Src/config/logging_config.py` (arquivo `logs/app.log` rotativo). Em blocos
  `except`, use `logger.exception(...)`, nunca `print`.
- **Tema do desktop**: `Src/config/ui_theme.py` centraliza cores, tipografia e espaçamento.
- **Banco**: `DatabasePMPV` é um context manager (`with DatabasePMPV() as db:`), usa WAL e tem
  `backup()`. Nomes de tabela em SQL são validados por allow-list. Local: `pmpv_data.db` na raiz;
  no Railway: volume `/data` (variável `PLATAFORMA_DB`); banco inicial em `seed/`.
- **Períodos**: sempre normalizados por `Src/common/periodos.py` ("Out/2025"). Há dois calendários:
  trimestres da tarifa (Nov–Jan, Fev–Abr, Mai–Jul, Ago–Out) para PMPV, PR e PV, e trimestres civis
  (Jan–Mar…) para SCG e SR.

## Dívida técnica conhecida (13/11/2026)

A estrutura de pastas segue a arquitetura, mas **parte das dependências ainda atravessa camadas**.
Estes arquivos criam `DatabasePMPV()` direto, contra a regra acima (entre parênteses, quantas vezes):

| Camada | Arquivos |
|---|---|
| Services | `servicos_auditoria_lote.py` (6), `servicos_concilia_lote.py` (5), `servicos_ret_lote.py` (4), `servicos_cgf.py` (3), `servicos_scg.py` (2), `servicos_margem.py` (2), `servicos_pmpv.py` (1), `servicos_periodos.py` (1) |
| Views (desktop) | `tela_sr.py` (5), `tela_auditoria.py` (2), `tela_concilia.py` (2), `tela_ret.py` (2), `tela_cgf.py` (1), `tela_pr.py` (1), `tela_scg.py` (1), `dashboard_resumo.py` (1) |
| API | `routers/auditoria.py` (1), `dashboard_extra.py` (1) |
| Outros | `common/excel_final_destino.py` (4), `exporters/excel_consolidado.py` (1), `exporters/nota_tecnica.py` (1) |

Usos legítimos: `Database/database.py`, `infrastructure/repositories/sqlite_repositories.py` e
`api/serve.py` (preparo do banco ao subir o servidor).

Ordem sugerida para pagar a dívida, um arquivo por vez e sem mudar resultado: primeiro os Services
do ciclo que o site mais usa (`servicos_cgf`, `servicos_auditoria_lote`, `servicos_concilia_lote`,
`servicos_ret_lote`), depois `servicos_scg`, por último as Views do desktop.

Outros pontos:
- `DatabasePMPV` (~1.350 linhas) conhece todas as tabelas. O caminho é dividi-lo por agregado; como
  os repositórios já isolam as camadas de cima, a migração pode ser gradual.
- O `commit` é feito por método no `DatabasePMPV`; transações compostas ainda não são controladas
  por quem chama.
- As Views do desktop são grandes (~5.400 linhas no total) e algumas ainda têm cálculo próprio
  (ex.: `tela_sr.py` e `tela_pr.py` com a fórmula antiga do PR e gravação a cada tecla). Devem
  passar a chamar os mesmos Services/Use Cases que a API usa.
