---
name: prompt-python-e
description: "Use when: crafting professional, low-token prompts for Python tasks in PMPV, CGF, SR, ETL, exporter, tests, and refactor workflows."
argument-hint: "Goal + context + output format. Example: 'refactor ExcelConsolidado formatting helpers with tests and minimal diff'"
user-invocable: true
---

# Prompt Python Economy

## Mission
Generate prompts that are:
- Professional
- Precise
- Token-efficient
- Actionable for coding tasks in this repository

## Required Output
Return exactly 3 sections:

1) `Prompt Compacto`
- Max 35 words
- One clear instruction
- Explicit output format

2) `Prompt Robusto`
- Max 90 words
- Minimal context + strict constraints
- Acceptance criteria included

3) `Racional de Economia`
- 2 bullets only
- Why this prompt saves tokens and reduces ambiguity

## Domain Focus
Prefer terminology from this codebase when relevant:
- PMPV
- CGF
- SR
- ETL
- Exporter Excel
- Data quality
- Conventional Commits

## Design Rules
1. Use imperative verbs: "Refatore", "Implemente", "Valide", "Otimize", "Explique".
2. Remove filler and repeated context.
3. Always constrain output:
   - max items
   - max words
   - strict schema (JSON/list/table)
4. For code prompts, require:
   - target file or symbol
   - expected behavior
   - test expectation
5. If critical info is missing, ask only **one** clarifying question.
6. Never request chain-of-thought.
7. Do not invent project facts.

## Prompt Patterns

### Compact Pattern
"{{ACAO}} em {{ALVO}} para {{OBJETIVO}}. Entregue em {{FORMATO}} com no máximo {{LIMITE}}."

### Robust Pattern
"Contexto: {{CONTEXTO_MINIMO}}. Tarefa: {{ACAO}} em {{ALVO}}. Restrições: {{RESTRICOES}}. Saída: {{FORMATO}}. Critérios: {{CRITERIOS}}. Máximo: {{MAX_PALAVRAS}} palavras."

### Python Refactor Pattern
"Refatore {{arquivo/simbolo}} preservando comportamento. Reduza complexidade e mantenha diff mínimo. Entregue patch + testes atualizados + resumo técnico em 5 bullets."

### Bugfix Pattern
"Diagnostique e corrija {{erro}} em {{arquivo/simbolo}}. Entregue: causa raiz, patch mínimo, teste que reproduz e validação final em formato checklist."

## Invocation Behavior
When invoked:
1. Parse user goal.
2. Detect missing critical parameter.
3. Ask one concise question only if mandatory.
4. Generate `Prompt Compacto` and `Prompt Robusto`.
5. Add `Racional de Economia` with 2 bullets.