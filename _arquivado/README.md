# Código arquivado

Esta pasta contém código **descontinuado**, mantido apenas como referência histórica.
Não faz parte do sistema em execução e não deve ser importado por nenhum módulo ativo.

## `backend/` — pipeline Airflow + Postgres (arquivado em 2026-06-08)

Era um segundo motor de ETL (Airflow + Postgres + Docker) que processava os mesmos
módulos da conta gráfica (Auditoria, RET, CGF, Conciliação, PMPV) **em paralelo** ao
app desktop e ao `pipeline.py`.

### Por que foi arquivado

1. **Duplicação de regra de negócio.** Os cálculos viviam em dois lugares:
   `Src/Services/*` (fonte oficial, usada pelo app e pelo `pipeline.py`) e
   `backend/etl/transformers/*` (cópia independente). Toda mudança de regra precisava
   ser feita duas vezes.

2. **As duas versões já tinham divergido.** Exemplo concreto no CGR (Auditoria):
   - `Src/Services/servicos_auditoria.py` deriva o ICMS da taxa
     (`valor × icms_taxa`, tratando CSTs de isenção) — e documenta explicitamente
     *"não usar o vICMS do XML diretamente"*.
   - `backend/etl/transformers/auditoria_transform.py` usava `vICMS` bruto do XML.

   Mesma fórmula final, entrada diferente → **CGR diferente**. Em um sistema de conta
   gráfica, divergência silenciosa de número é o pior defeito possível.

3. **Peso operacional desproporcional.** Airflow exige Docker + Postgres + manutenção,
   enquanto o problema real (fechamento mensal numa máquina Windows) é resolvido pelo
   `pipeline.py` + Task Scheduler + SQLite a custo zero.

### Fonte de verdade atual

| Função | Caminho ativo |
|---|---|
| Regras de cálculo | `Src/Services/*` |
| Automação do fechamento | `pipeline.py` (raiz) + `instalar_agendamento.py` |
| Banco | SQLite (`pmpv_data.db`) via `Src/Database/database.py` |

### Como restaurar (se um dia precisar de orquestração distribuída)

```bash
git mv _arquivado/backend backend
```

Antes de reativar, **unifique os cálculos**: faça os DAGs/transformers chamarem
`Src/Services/*` em vez de manter lógica própria, para a divergência não voltar.
