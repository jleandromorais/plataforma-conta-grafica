> **Status (2026-08-04):** implementados PMPV (parcial), SCG, PR, PV, RPV,
> SR-sessão, Dashboard e Config — todos os módulos que já tinham
> Service/Repository/Use Case prontos, seguindo a regra do §3 (nenhuma rota
> chama `DatabasePMPV` direto). Código em `Src/api/`. Pendente: CGF,
> Auditoria, Conciliação, RET, SR-trimestre, PMPV-trimestre-ativo e
> PMPV-importar-memoria — todos marcados com `TODO(spec §...)` no código,
> pois exigem criar Repository/Use Case novo primeiro (trabalho do §5).
> Ver "Como rodar" no final deste arquivo.

# Spec — Backend FastAPI sobre `Src/Services`

Referente à task:

> ## 0. Pré-requisito
> - [ ] Backend FastAPI expondo os endpoints já assumidos em `src/api/index.ts`,
>       construído sobre `Src/Services` (fonte única dos cálculos).

Base factual: levantamento de `Src/Services`, `Src/domain`, `Src/application`,
`Src/infrastructure`, `Src/Database`, `Src/config`, `Src/common` e cruzamento
com `Src/Views/tela_*.py` (2026-08-04).

---

## 1. Estado atual da arquitetura (por que isso não é um CRUD trivial)

O projeto já segue Clean Architecture, mas **de forma incompleta e
inconsistente entre módulos**:

| Módulo | Domain/Ports | Repository | Use Case | Acesso direto a `DatabasePMPV` na View? |
|---|---|---|---|---|
| PMPV | ✅ `PMPVRepository` | ✅ `SqlitePMPVRepository` | ✅ `PMPVUseCases` | Sim (import tardio, adicional) |
| Consolidação (CGR/CGF/RET/RP/RPV/SCG) | ✅ `ConsolidacaoRepository` | ✅ `SqliteConsolidacaoRepository` | ❌ | Sim (SCG, RET, Concilia, Auditoria passam por cima) |
| PR | ✅ `PRRepository` | ✅ `SqlitePRRepository` | ❌ | Sim |
| PV | ✅ `PRRepository` (compartilhado) | ✅ `SqlitePRRepository` | ❌ | **Não** — único módulo limpo ponta a ponta |
| RPV | — (usa `ServicosConsolidacao`) | — | ❌ | **Não** — único módulo limpo ponta a ponta |
| SR (sessão VP/VF) | ✅ `SRRepository` | ✅ `SqliteSRRepository` | ❌ | Sim |
| SR (trimestre, com Selic) | ❌ | ❌ | ❌ | **Sim, 100%** — toda a lógica está na View |
| CGF | ❌ | ❌ | ❌ | Sim (`cgf_resumo` não tem Service) |
| RET | ❌ | ❌ | ❌ | Sim (`ret_itens` não tem Service/Repository) |
| Conciliação | ❌ | ❌ | ❌ | Sim (`concilia_itens` não tem Repository) |
| Auditoria | ❌ | ❌ | ❌ | Sim (`auditoria_itens` não tem Repository) |

**Decisão arquitetural desta spec:** a API **não** vai replicar chamadas
diretas a `DatabasePMPV` dentro das rotas. Cada endpoint que hoje só existe
como código dentro de uma View Tkinter primeiro ganha um método de
Repository (implementando o port correspondente, criando o port quando não
existe) e, quando há orquestração de múltiplos passos, um Use Case. As rotas
FastAPI chamam **apenas** `application/use_cases` ou, na ausência de um caso
de uso dedicado, um Service/Repository — nunca `Database.database.DatabasePMPV`
diretamente. Isso termina o trabalho de Clean Architecture que os módulos
mais antigos (CGF, RET, Concilia, Auditoria, SR-trimestre) deixaram
incompleto, em vez de perpetuar o atalho.

Consequência prática: para módulos como RET e Auditoria, boa parte do
esforço da API é **extrair a lógica que hoje mora na View** para
Service/Repository novos — não é só "escrever uma rota".

---

## 2. Stack e estrutura de diretórios proposta

```
Src/api/
  __init__.py
  main.py                 # instancia FastAPI, monta routers, CORS, exception handlers
  deps.py                 # dependency injection (DatabasePMPV, repos, services)
  schemas/                 # Pydantic models — request/response por módulo
    pmpv.py
    cgf.py
    auditoria.py
    concilia.py
    ret.py
    scg.py
    pr.py
    pv.py
    rpv.py
    sr.py
    dashboard.py
  routers/
    pmpv.py
    cgf.py
    auditoria.py
    concilia.py
    ret.py
    scg.py
    pr.py
    pv.py
    rpv.py
    sr.py
    dashboard.py
  errors.py                # mapeamento de exceções de domínio -> HTTPException
```

- **Framework**: FastAPI + Uvicorn.
- **Validação**: Pydantic v2 (schemas espelhando os `types/index.ts` do
  front — ver §4, tabela de contrato).
- **Banco**: mantém `DatabasePMPV`/SQLite como está — não é escopo desta
  task migrar de storage.
- **Upload de arquivos**: `UploadFile` do FastAPI para CGF/Auditoria/
  Conciliação/RET (multipart), gravando em diretório temporário antes de
  chamar os Services (que hoje recebem `Path`/`str` de caminho local).
- **CORS**: liberar origem do Vite dev server (`http://localhost:5173` por
  padrão) — necessário porque o front já assume `VITE_API_URL` separado.
- **Docs**: `/docs` (Swagger) e `/openapi.json` nativos do FastAPI — o front
  pode gerar tipos TS a partir do OpenAPI no futuro (fora de escopo agora).

---

## 3. Regra de mapeamento View → Endpoint

Cada rota deve:
1. Ser um wrapper fino sobre Use Case (preferencial) ou Service/Repository.
2. Não conter lógica de negócio (fórmulas, validações de domínio) — isso já
   existe em `Src/Services` e deve continuar lá.
3. Traduzir exceções de domínio (`ValueError` etc., hoje capturadas com
   `messagebox.showerror` nas Views) em `HTTPException` com status
   apropriado (422 para dados inválidos, 404 para período/sessão
   inexistente, 500 para erro inesperado).
4. Onde a View faz a orquestração hoje (ex.: `tela_pmpv.py` chamando
   `ExcelPMPV.ler_dados_memoria_calculo` → `RegrasPMPV.calcular_resultados`
   → `PMPVUseCases.salvar_sessao_completa`), essa orquestração deve migrar
   para um Use Case (novo, se não existir), não para dentro do router.

---

## 4. Contrato de endpoints (por módulo)

Convenção de status: `200` sucesso leitura, `201` criação, `204` sucesso sem
corpo, `404` recurso não encontrado, `422` erro de validação/negócio (ex.:
`ValueError("Volume Zero...")`).

### 4.1 PMPV
Já tem Use Case pronto (`PMPVUseCases`) — módulo mais barato de expor.

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/pmpv/calcular` | POST | `PMPVUseCases.calcular_resultados` (novo wrapper, hoje staticmethod puro) | `{dados_extraidos, valor_cg, dias_config, lista_meses, idx_start}` | dict de `RegrasPMPV.calcular_resultados` (`pmpv`, `preco_final`, `vp_mensal`, `vp_por_mes`, `avisos`, ...) |
| `/pmpv/salvar` | POST | `PMPVUseCases.salvar_sessao_completa` | `{nome, dados_por_mes, resultado}` | `{sessao_id}` |
| `/pmpv/mensal/{periodo}` | GET | `SqlitePMPVRepository.buscar_pmpv_mensal` | — | `{pmpv}` ou 404 |
| `/pmpv/mensal/{periodo}` | POST | `PMPVUseCases.salvar_pmpv_mensal` | `{pmpv}` | 204 |
| `/pmpv/importar-memoria` | POST | `ExcelPMPV.ler_dados_memoria_calculo` (novo wrapper de use case) | multipart: arquivo + `mes_escolhido` | `dict[empresa, {mol, trans, log, volume}]` |
| `/pmpv/periodos` | GET | `SqlitePMPVRepository.listar_periodos` | — | `list[str]` |
| `/pmpv/trimestre-ativo` | GET/POST | `DatabasePMPV.buscar_trimestre_ativo`/`salvar_trimestre_ativo` (**precisa de método novo em `PMPVRepository`/port** — hoje só existe direto no banco) | `{meses: list[str]}` (POST) | `{meses: list[str]}` |

⚠️ Front hoje hardcoda `TRIMESTRES` em `PMPV/index.tsx` — expor
`GET /config/trimestres-fiscais` (lendo `Src/common/periodos.py`,
`TRIMESTRES_FISCAIS`/`TRIMESTRES_FISCAIS_ABREVS`) para eliminar a duplicação
sinalizada na auditoria do front.

### 4.2 CGF — requer novo Repository (`CGFRepository`/`SqliteCGFRepository`)
Hoje `ServicosCGF` cobre parte, mas `tela_cgf.py` acessa `DatabasePMPV`
direto para `cgf_resumo` (`salvar_cgf_resumo`, `buscar_cgf_resumo`,
`listar_cgf_resumos`) e para configuração de colunas.

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/cgf/processar` | POST | `ServicosCGF.processar_arquivos` | multipart: arquivos + `fat_col, fat_cons_col, fat_cons_val, canc_col, dev_col` | `{logs, volume_final, volume_faturado, volume_canceladas, volume_devolucoes, volume_consumo_proprio}` |
| `/cgf/salvar` | POST | `ServicosCGF.salvar_cgf` (grava `cgf_resumo` completo, não só `volume`+`cgf`; **conferir se `salvar_cgf` precisa de assinatura estendida** para os 5 volumes) | `{periodo, volume_faturado, volume_canceladas, volume_devolucoes, volume_consumo_proprio, volume_final, pmpv}` | `{cgf_rs, rpv}` |
| `/cgf/resumos` | GET | `DatabasePMPV.listar_cgf_resumos` (**novo método no Repository**) | — | `list[CGFResumo]` |
| `/cgf/pmpv/{periodo}` | GET | `ServicosCGF.buscar_pmpv` | — | `{pmpv}` |
| `/cgf/periodos` | GET | `ServicosCGF.obter_periodos` | — | `list[str]` |

### 4.3 Auditoria — requer novo `AuditoriaRepository`
`auditoria_itens` hoje só existe em `DatabasePMPV` (`salvar_auditoria_itens`,
`listar_auditoria_itens`, `listar_periodos_auditoria`), chamado direto pela
View. `RegrasAuditoria` é puramente funcional (parsers), sem persistência.

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/auditoria/processar` | POST | `RegrasAuditoria.parse_nfe`/`parse_cte`/`parse_pdf_ocr` (por arquivo) + `empresa_integra_cgr` + `RegrasAuditoria.calcular_cgr_liquido` (orquestração hoje na View → **vira novo Use Case** `AuditoriaUseCases.processar_arquivos`) | multipart: arquivos + `periodo` + `modo` (XML/PDF-OCR) | `AuditoriaResultado` (`cgr_liquido, valor_total_nfe, valor_total_cte, volume_total, itens, periodo`) |
| `/auditoria/comparar` | POST | `ComparadorContaGrafica.comparar` | `{periodo}` + multipart planilha Excel | `ResultadoComparacaoNotas` |
| `/auditoria/salvar` | POST | `DatabasePMPV.salvar_auditoria_itens` (via novo `AuditoriaRepository`) | `AuditoriaResultado` | 204 |
| `/auditoria/periodos` | GET | `listar_periodos_auditoria` (via repo novo) | — | `list[str]` |
| `/auditoria/exportar` | POST | `ExcelAuditoria.gerar_relatorio_auditoria` | `{periodo}` | arquivo `.xlsx` (`FileResponse`) ou `{caminho}` se mantido em disco compartilhado |

### 4.4 Conciliação — requer novo `ConciliaRepository`

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/conciliacao/processar` | POST | `RegrasConcilia.processar_arquivos` | multipart: arquivos + `categoria` | `ConciliaResultado` (itens tipados de `PdfItem`) |
| `/conciliacao/salvar` | POST | `DatabasePMPV.salvar_concilia_itens` (via repo novo) + `ServicosConsolidacao.salvar_rp`-equivalente | `ConciliaResultado` | `{saldo_rp}` |
| `/conciliacao/exportar` | POST | `ExcelConcilia.gerar_relatorio` | `{periodo}` | arquivo `.xlsx` |

### 4.5 RET — requer novo `RETRepository`

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/ret/processar` | POST | `RegrasRET.identificar_tipo`/`extrair_dados_pdf` por arquivo + `RegrasRET.calcular_ret` (orquestração da View → **novo Use Case** `RETUseCases.processar_arquivos`) | multipart: arquivos + `periodo` | `RETResultado` (`eat_bruto, ret, pis_cofins_rate, itens, periodo`) |
| `/ret/salvar` | POST | `DatabasePMPV.salvar_ret_itens` (via repo novo) | `RETResultado` | 204 |
| `/ret/exportar` | POST | `ExcelRET.gerar_relatorio_completo` | `{periodo}` | arquivo `.xlsx` |

⚠️ Front hardcoda `PIS_COFINS_RATE = 0.0465` em `RET/index.tsx` — valor real
em `servicos_ret.py` é `0.0925`. Expor via `GET /config/taxas` (ver §4.9)
para eliminar a divergência já sinalizada na auditoria.

### 4.6 SCG — usa `ServicosSCG`, mas SR-trimestre-relacionado ainda falta

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/scg/periodos` | GET | `ServicosSCG.obter_periodos` | — | `list[SCGPeriodo]` |
| `/scg/{periodo}` | GET | `ServicosSCG.buscar_dados_periodo` | — | `SCGPeriodo` ou 404 |
| `/scg/calcular/{periodo}` | POST | `ServicosSCG.calcular_scg_oficial` | — | `SCGPeriodo` |
| `/scg/manual` | POST | `ServicosSCG.salvar_valores_manuais` | `{periodo, cgr, cgf, ret, rp}` | `{rpv}` |
| `/scg/{periodo}` | DELETE | `ServicosSCG.apagar_periodo` | — | 204 |
| `/scg/trimestre-ativo` | POST | Reaproveita `/pmpv/trimestre-ativo` (mesma tabela `config`) | — | — |

### 4.7 PR

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/pr/{periodo}` | GET | `ServicosPR.buscar_dados_periodo` | — | `PRResultado` (`scg, sr, vp, pr`) ou 404 |
| `/pr/trimestral` | POST | `ServicosPR.buscar_dados_trimestral` | `{periodos: list[str]}` | `{scg, sr, vp, pr, meses, meses_sem_vp}` |
| `/pr/salvar` | POST | `ServicosPR.salvar_valores` | `{periodo, scg, sr, vp}` | `{pr}` |
| `/pr/periodos` | GET | `ServicosPR.obter_todos_periodos` | — | `list[str]` |

### 4.8 PV

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/pv/{periodo}` | GET | `ServicosPV.buscar_dados_periodo` | — | `{pmpv, pr, pv}` ou 404 |
| `/pv/salvar` | POST | `ServicosPV.salvar_valores` | `{periodo, pmpv, pr}` | `{pv}` |
| `/pv/periodos` | GET | `ServicosPV.obter_periodos` | — | `list[dict]` |

### 4.9 RPV

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/rpv/{periodo}` | GET | `ServicosRPV.buscar_dados_periodo` | — | `{cgr, cgf, rpv}` ou 404 |
| `/rpv/salvar` | POST | `ServicosRPV.salvar_valores` | `{periodo, cgr, cgf}` | `{rpv}` |
| `/rpv/periodos` | GET | `ServicosRPV.obter_periodos` | — | `list` |

### 4.10 SR — dois sub-recursos distintos (sessão VP/VF vs trimestre com Selic)
⚠️ Confirma o achado da auditoria do front: **o cálculo real de SR usa
VP/VF/PR/SELIC/SR-anterior, não CGR/CGF/RPV**. A API deve seguir esse
contrato, não o que está hoje em `SR/index.tsx`.

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/sr/sessoes` | GET | `ServicosSR.listar_sessoes` | — | `list[{id, nome, data_criacao, vp, vf}]` |
| `/sr/sessoes/{id}/vp-vf` | GET | `ServicosSR.buscar_vp_vf` | — | `{vp, vf}` |
| `/sr/calcular` | POST | `ServicosSR.calcular_sr` (puro) | `{vp, vf, pr}` | `{sr}` |
| `/sr/trimestre/{trimestre}` | GET | `DatabasePMPV.buscar_sr_trimestre`/`listar_sr_trimestres` (**precisa de novo `SRRepository.buscar/listar_trimestre` + novo Use Case** consolidando a lógica hoje em `tela_sr.py`: `diferença = VP-VF`, `sr_parcela = diferença × PR`, `sr_selic = sr_parcela × (1+selic) + sr_anterior`) | — | `list[{mes, vp, vf, pr, selic_mensal, diferenca, sr_parcela, sr_selic, sr_anterior, total}]` |
| `/sr/trimestre` | POST | idem, `salvar_sr_trimestre` via repo novo | `{trimestre, mes, vp, vf, pr, selic_mensal, sr_anterior}` | linha calculada e persistida |

### 4.11 Dashboard
⚠️ Confirma achado da auditoria: modelo real é CGR/RET/CGF/RP/RPV/SCG
mensais + PMPV, com filtro de ano — não "parcela de recuperação"/"SR total"
que hoje está mockado no front.

| Rota | Método | Fonte | Request | Response |
|---|---|---|---|---|
| `/dashboard` | GET | Novo Use Case `DashboardUseCases.montar_resumo` agregando `DatabasePMPV.listar_consolidacao_completa` + `listar_pmpv_mensal` (**não existe hoje, precisa ser escrito** — a View monta isso inline em `dashboard_resumo.py`) | query `?ano=` (opcional, "todos" se omitido) | KPIs mensais (CGR, RET, CGF, RP, RPV, SCG, variação % vs mês anterior) + série PMPV + série SCG |

### 4.12 Config (novo, transversal)
Elimina duplicação de regra de negócio hardcoded no front, sinalizada na
auditoria (trimestres em PMPV, taxa PIS/COFINS em RET).

| Rota | Método | Fonte | Response |
|---|---|---|---|
| `/config/trimestres-fiscais` | GET | `Src/common/periodos.py`, `TRIMESTRES_FISCAIS_ABREVS` | `[{label, meses: [str,str,str]}]` |
| `/config/trimestres-civis` | GET | `TRIMESTRES_CIVIS` | idem |
| `/config/taxas` | GET | `PIS_COFINS_RATE` (ret), `PIS_RATE`/`COFINS_RATE` (auditoria), `TAXA_EUR_BRL` | `{pis_cofins_rate_ret, pis_rate_auditoria, cofins_rate_auditoria, taxa_eur_brl}` |

---

## 5. Trabalho de extração necessário antes/durante a implementação

Não é só "escrever routers". Por módulo, o que precisa ser criado em
`Src/domain/ports`, `Src/infrastructure/repositories` e
`Src/application/use_cases` **antes** da rota poder existir sem violar a
regra do §3:

1. **CGF**: `CGFRepository` (port) + `SqliteCGFRepository` cobrindo
   `salvar_cgf_resumo`, `buscar_cgf_resumo`, `listar_cgf_resumos`.
2. **Auditoria**: `AuditoriaRepository` (port) + `SqliteAuditoriaRepository`
   cobrindo `salvar_auditoria_itens`, `listar_auditoria_itens`,
   `listar_periodos_auditoria`; `AuditoriaUseCases` para orquestrar
   parse → cálculo CGR líquido → (opcional) comparação com Excel.
3. **Conciliação**: `ConciliaRepository` (port) + `SqliteConciliaRepository`
   cobrindo `salvar_concilia_itens`, `listar_concilia_itens`,
   `listar_periodos_concilia`.
4. **RET**: `RETRepository` (port) + `SqliteRETRepository` cobrindo
   `salvar_ret_itens`, `listar_ret_itens`, `listar_periodos_ret`;
   `RETUseCases` para orquestrar identificação de tipo → extração OCR →
   cálculo EC/RET.
5. **SR-trimestre**: estender `SRRepository` (port) com
   `buscar_sr_trimestre`, `salvar_sr_trimestre`, `listar_sr_trimestres`;
   `SRUseCases` para a fórmula completa com Selic (hoje só em `tela_sr.py`).
6. **PMPV**: estender `PMPVRepository` com `buscar_trimestre_ativo`/
   `salvar_trimestre_ativo` (hoje só em `DatabasePMPV`, chamado direto pela
   View e também usado pelo módulo SCG).
7. **Dashboard**: novo `DashboardUseCases`, sem port de repositório próprio
   — reaproveita `ConsolidacaoRepository` + `PMPVRepository` já existentes.

Cada item acima segue o padrão já estabelecido por
`SqliteConsolidacaoRepository`/`SqlitePMPVRepository` (wrapper fino sobre
`DatabasePMPV`, sem lógica própria) — não é redesenho de arquitetura, é
completar o padrão existente para os módulos que pularam essa etapa.

---

## 6. Fora de escopo desta task (registrar, não implementar agora)
- Autenticação/autorização (não há hoje nas Views, é app local single-user).
- Migração de storage (SQLite continua).
- Deploy/infra (Docker, hosting) — spec cobre só a API em si.
- Reescrever `ExcelPMPV`/`ExcelAuditoria`/`ExcelConcilia`/`ExcelRET` para
  retornar bytes em memória em vez de gravar em disco — manter geração em
  disco por ora, API expõe via `FileResponse`.

## 7. Critério de pronto (Definition of Done) desta task
- [ ] Todos os endpoints da tabela §4 implementados e respondendo conforme
      contrato.
- [ ] Nenhum router chama `DatabasePMPV` diretamente (checagem manual/grep).
- [ ] Repositórios/Use Cases novos do §5 têm teste unitário cobrindo pelo
      menos o caminho feliz.
- [ ] `GET /docs` (Swagger) funcional, refletindo os schemas Pydantic.
- [ ] `src/api/index.ts` do front consegue apontar `VITE_API_URL` para o
      servidor local e o Dashboard/PMPV carregam dado real (smoke test manual).
- [ ] `/config/trimestres-fiscais` e `/config/taxas` existem e o front passa
      a consumi-los em vez dos valores hardcoded sinalizados na auditoria
      (item tratado nas tasks específicas de PMPV/RET do `TASKS.md`, não
      nesta task — aqui só garantir que o endpoint existe).

---

## 8. Como rodar (implementado nesta rodada)

```
pip install -r requirements.txt   # inclui fastapi/uvicorn/python-multipart
uvicorn Src.api.main:app --reload --port 8080
```

- Swagger: `http://localhost:8080/docs`
- Health check: `GET http://localhost:8080/api/health`
- CORS liberado por padrão para `http://localhost:5173` (Vite dev server);
  ajustável via env var `CORS_ORIGINS` (lista separada por vírgula).

### Módulos prontos (smoke-tested contra `pmpv_data.db` real)
PMPV (exceto trimestre-ativo/importar-memoria), SCG, PR, PV, RPV, SR-sessão,
Dashboard, Config.

### Módulos pendentes (stubs com TODO no código, sem rota registrada)
CGF, Auditoria, Conciliação, RET, SR-trimestre — todos exigem primeiro criar
o Repository (e, em alguns casos, Use Case) correspondente listado no §5,
porque hoje essa lógica só existe dentro das Views Tkinter chamando
`DatabasePMPV` direto. Não foram implementados nesta rodada para não violar
a regra do §3 (nenhuma rota chama o banco diretamente) nem escrever
extração de lógica de negócio sem poder testar contra dados reais.
