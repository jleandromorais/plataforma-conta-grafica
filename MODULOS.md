# Separação em Módulos — GraphAccount Pro

Documento de design para a reorganização lógica do sistema em três módulos coesos.
A estrutura de pastas existente em `Src/Services/` **não muda** — o que muda é a
leitura mental do sistema e, futuramente, a organização em sub-pacotes.

---

## Visão geral

```
┌──────────────────────────────────────────────────────────────────┐
│  MÓDULO 1 — PMPV (Precificação Mensal por Volume)                │
│  Entrada de dados mensais por empresa                             │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ alimenta
┌──────────────────────────────────▼───────────────────────────────┐
│  MÓDULO 2 — Cálculos Mensais (7 sub-módulos)                     │
│  2.1 CGR · 2.2 CGF · 2.3 RPV · 2.4 RET · 2.5 RP · 2.6 SCG · 2.7 SR │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ consolida em
┌──────────────────────────────────▼───────────────────────────────┐
│  MÓDULO 3 — Parcela de Recuperação / Consolidação Trimestral      │
│  3.1 Atualização SCG · 3.2 VP · 3.3 Soma (SCG+SR+VP) · 3.4 PR  │
└──────────────────────────────────────────────────────────────────┘
```

---

## MÓDULO 1 — PMPV (Precificação Mensal por Volume)

**Responsabilidade:** Capturar e persistir os dados mensais de volume e preço por
empresa. É a **fonte primária** de dados para todos os cálculos posteriores.

| Artefato | Caminho atual |
|---|---|
| Serviço principal | `Src/Services/servicos_pmpv.py` → `ExcelPMPV`, `ServicosPMPV` |
| Use case | `Src/application/use_cases/pmpv_use_cases.py` |
| View | `Src/Views/tela_pmpv.py` |
| Exportação | `Src/infrastructure/exporters/excel_handler_pmpv.py` |

**O que faz:**
- Lê planilhas Excel com volumes mensais por empresa (`ExcelPMPV._normalizar_mes`)
- Salva os registros na tabela `pmpv_mensal` via `PMPVRepository`
- Calcula o PMPV acumulado mensal que serve de base para o Módulo 3

**Dado de saída:** `pmpv_mensal(periodo, empresa, volume, preco_unitario)`

---

## MÓDULO 2 — Cálculos Mensais

**Responsabilidade:** Executar os 7 cálculos mensais da conta gráfica, cada um
dependendo dos dados brutos do Módulo 1 ou de planilhas externas.
Todos os resultados são persistidos na tabela de consolidação.

### 2.1 CGR — Custo Gerenciável Real

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_consolidacao.py` (campo `cgr`) |
| View | `Src/Views/tela_scg.py` (entrada manual do CGR) |

- Valor informado ou importado que representa o custo real gerenciável do período.
- Persiste em `consolidacao.cgr`.

---

### 2.2 CGF — Custo Gerenciável Fixado

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_cgf.py` → `ServicosCGF` |
| View | `Src/Views/tela_cgf.py` |

- Lê planilhas Excel/CSV e normaliza valores numéricos (pt-BR → float).
- Salva o CGF em `consolidacao.cgf` via `ServicosConsolidacao`.

---

### 2.3 RPV — Resultado de Preço Variável

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_rpv.py` → `ServicosRPV` |
| Cálculo puro | `ServicosConsolidacao.calcular_rpv(cgr, cgf)` |
| View | `Src/Views/tela_rpv.py` |

- **Fórmula:** `RPV = CGR − CGF`
- Derivado automaticamente dos campos 2.1 e 2.2 sempre que a consolidação é lida.

---

### 2.4 RET — Remuneração por Eficiência Técnica

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_ret.py` |
| View | `Src/Views/tela_ret.py` |
| Exportação | `Src/Services/excel_ret.py` |

- Processa PDFs via OCR (`Src/infrastructure/ocr/ocr_pdf.py`, `gemini_pdf.py`).
- Aplica taxa EUR→BRL (`TAXA_EUR_BRL = 6.0`) e alíquota PIS/COFINS (`0.0925`).
- Salva `consolidacao.ret`.

---

### 2.5 RP — Receita de Parcela (input mensal)

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_consolidacao.py` (campo `rp`) |
| View | `Src/Views/tela_scg.py` (entrada junto ao CGR) |

- Valor informado manualmente para o período.
- Persiste em `consolidacao.rp`.

---

### 2.6 SCG — Saldo da Conta Gráfica

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_scg.py` → `ServicosSCG` |
| Cálculo puro | `ServicosConsolidacao.calcular_scg(cgr, cgf, ret, rp)` |
| View | `Src/Views/tela_scg.py` |

- **Fórmula:** `SCG = RPV + RET + RP`  (onde `RPV = CGR − CGF`)
- Calculado automaticamente após salvar qualquer componente.
- Persiste em `consolidacao.scg`.

---

### 2.7 SR — Saldo de Recuperação

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_sr.py` → `ServicosSR` |
| View | `Src/Views/tela_sr.py` |

- **Fórmula:** `SR = (VP − VF) × PR`
  - `VP`: Volume Produzido (soma dos volumes de todas as empresas da sessão PMPV)
  - `VF`: Volume Faturado (volume real do trimestre)
  - `PR`: Preço Regulatório (vindo do sub-módulo 3.4)
- Depende do resultado do Módulo 3 para o `PR` — existe dependência cruzada
  intencional: SR usa o PR consolidado do trimestre anterior.

---

## MÓDULO 3 — Parcela de Recuperação / Consolidação Trimestral

**Responsabilidade:** Agregar os dados mensais do Módulo 2 em uma visão trimestral
e calcular a Parcela de Recuperação final.

### 3.1 Atualização SCG

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_consolidacao.py` → `ServicosConsolidacao` |
| Exportação | `Src/infrastructure/exporters/excel_consolidado.py` |
| View | `Src/Views/tela_scg.py` |

- Lê todos os períodos mensais e garante consistência dos campos
  (`_normalizar_dados`): recalcula RPV e SCG se divergentes.
- Prepara o SCG trimestral somando os 3 meses do período.

---

### 3.2 Cálculo VP (Volume Produzido trimestral)

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_sr.py` → `ServicosSR.buscar_vp_vf` |
| Repositório | `SRRepository.listar_sessoes_com_volumes()` |
| View | `Src/Views/tela_sr.py` |

- Agrega o VP de todos os meses do trimestre a partir das sessões PMPV salvas.
- O VP trimestral é usado no cálculo do SR (2.7) e do PR (3.4).

---

### 3.3 Soma Trimestral — SCG + SR + VP

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_pr.py` → `ServicosPR` (usa SCG + SR) |
|          | `Src/Services/servicos_pv.py` → `ServicosPV` (agrega PMPV + PR) |
| View | `Src/Views/tela_pr.py`, `Src/Views/tela_pv.py` |

- Agrega os três componentes do trimestre:
  - `SCG_trimestre` = soma dos `consolidacao.scg` dos 3 meses
  - `SR_trimestre` = `ServicosSR.calcular_sr(vp, vf, pr)`
  - `VP_trimestre` = volume total produzido do período
- Essa soma é o numerador do cálculo do PR.

---

### 3.4 PR — Preço Regulatório

| Artefato | Caminho atual |
|---|---|
| Serviço | `Src/Services/servicos_pr.py` → `ServicosPR` |
| View | `Src/Views/tela_pr.py` |

- **Fórmula:** `PR = (SCG + SR) / VP`
  - `SCG`: saldo da conta gráfica do trimestre (sub-módulo 3.1)
  - `SR`: saldo de recuperação (2.7)
  - `VP`: volume produzido trimestral (3.2)
- Retorna `0.0` quando `VP = 0` para evitar divisão por zero.
- O PR calculado alimenta o SR do próximo ciclo (dependência circular entre 2.7 e 3.4
  é resolvida usando o PR do trimestre **anterior** para calcular o SR **atual**).

---

## Dependências entre módulos

```
MÓDULO 1 (PMPV)
    │
    ├──► 2.1 CGR  ──┐
    ├──► 2.2 CGF  ──┼──► 2.3 RPV ──► 2.6 SCG ──► 3.1 SCG atualizado ──► 3.3 Soma
    ├──► 2.4 RET  ──┘                                                         │
    ├──► 2.5 RP   ────────────────────────────────────────────────────────────┤
    └──► VP/VF ──────────────────────────── 3.2 VP ──────────────────────────┤
                                                                               │
         PR(t-1) ────────────────────────── 2.7 SR ──────────────────────────┤
                                                                               │
                                                                         3.4 PR(t)
```

**Ciclo trimestral:**
1. Módulo 1 coleta dados mensais (3 meses).
2. Módulo 2 calcula CGR, CGF, RPV, RET, RP, SCG, SR para cada mês.
3. Módulo 3 consolida: atualiza SCG, agrega VP, soma tudo e deriva o PR.
4. O PR resultante (`t`) é usado como entrada do SR (`t+1`) no próximo trimestre.

---

## Regras de design que não mudam

1. **Fonte única de verdade:** toda fórmula vive em `Src/Services/`. Nunca duplicar
   em Views ou infraestrutura.
2. **Injeção de dependência:** Services recebem `repo=` no `__init__`; testáveis
   com fakes sem tocar no banco.
3. **Ordem de cálculo dentro do trimestre:**
   `CGR → CGF → RPV → RET → RP → SCG → VP → SR → PR`
4. **PR do trimestre anterior** deve estar salvo antes de calcular o SR do trimestre
   atual (`consolidacao.pr` ou `pr_resultados`).
