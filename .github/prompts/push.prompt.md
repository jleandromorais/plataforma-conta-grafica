---
mode: agent
description: "Executa workflow Git profissional: analisa alterações, gera Conventional Commits em português com detecção inteligente de escopo, faz commit e push. Use '/push' para commit+push ou '/push+pr' para também abrir pull request."
tools: ["run_in_terminal", "get_changed_files"]
tags: ["git", "automation", "devops"]
---

# Workflow Profissional de Git Push

## Comportamento Principal

Quando invocado como `/push`: Executa workflow completo de commit + push.
Quando invocado como `/push+pr`: Executa push + cria pull request automaticamente.

**REGRA ABSOLUTA**: Todas as mensagens de commit devem ser escritas em **português brasileiro (pt-BR)**, seguindo Conventional Commits.

## Etapas de Execução

### Fase 1: Validação Pré-voo

Execute **todos** os comandos abaixo em sequência:

```
git rev-parse --abbrev-ref HEAD
git status --porcelain
git log --oneline -1
```

**Critérios de bloqueio** (não prosseguir):
- Se `git status --porcelain` retornar vazio → informar "Nenhuma alteração para commitar"
- Se existirem conflitos de merge (`UU` no status) → informar e abortar

**Alertas** (prosseguir com aviso):
- Se branch for `main` ou `master` → avisar e pedir confirmação explícita
- Se houver arquivos binários grandes (>.db, .exe, .zip) → avisar

### Fase 2: Análise das Alterações

1. Executar `git add .` para preparar todas as alterações
2. Executar `git diff --cached --stat` para obter resumo estatístico
3. Executar `git diff --cached --name-status` para categorizar cada arquivo:
   - `A` = Adicionado, `M` = Modificado, `D` = Removido, `R` = Renomeado
4. Usar a ferramenta `get_changed_files` para analisar o conteúdo das alterações em detalhe
5. Agrupar arquivos por área funcional (ver inferência de escopo abaixo)

### Fase 3: Geração do Commit

Construir mensagem de commit profissional e semântica.

**Formato obrigatório**: `<tipo>(<escopo>): <título em português>`

#### Inferência de Tipo

| Tipo       | Quando usar                                        |
|------------|-----------------------------------------------------|
| `feat`     | Novo arquivo, nova funcionalidade, nova capacidade  |
| `fix`      | Correção de bug, erro, comportamento incorreto      |
| `refactor` | Reestruturação sem mudança de comportamento          |
| `perf`     | Otimização de desempenho                             |
| `docs`     | Apenas documentação (README, comentários, prompts)   |
| `test`     | Adição ou modificação de testes                      |
| `ci`       | Pipelines, Docker, CI/CD, build                      |
| `style`    | Formatação, lint (sem mudança de lógica)             |
| `chore`    | Manutenção, dependências, configs gerais             |

#### Inferência de Escopo (por caminho dos arquivos)

| Caminho contém          | Escopo sugerido    |
|--------------------------|---------------------|
| `Src/Views/`            | `ui`               |
| `Src/Services/`         | `servicos`         |
| `Src/Database/`         | `banco`            |
| `Src/common/`           | `comum`            |
| `Src/config/`           | `config`           |
| `Src/domain/`           | `dominio`          |
| `Src/infrastructure/`   | `infra`            |
| `backend/etl/`          | `etl`              |
| `backend/data_quality/` | `qualidade-dados`  |
| `backend/monitoring/`   | `monitoramento`    |
| `backend/airflow/`      | `airflow`          |
| `tests/`                | `testes`           |
| `.github/`              | `ci`               |
| `Excel/`                | `excel`            |
| Múltiplos escopos       | usar o escopo principal ou `core` |

#### Regras do Título

- **Idioma**: Português brasileiro
- **Modo verbal**: Imperativo (ex: "adicionar", "corrigir", "melhorar", NÃO "adicionado", "corrigido")
- **Tamanho**: Máximo 72 caracteres na linha do título
- **Tom**: Técnico, claro, descritivo do valor da mudança
- **Caixa**: Minúsculas (exceto nomes próprios e siglas como PMPV, CGF, SR, SCG, RET)

#### Regras do Corpo (obrigatório se >3 arquivos ou >100 linhas alteradas)

- Linha em branco após o título
- Explicar **POR QUE** a mudança foi feita
- Descrever **O QUE** foi alterado (lista com `-`)
- Mencionar **IMPACTO** em outros módulos se aplicável
- Referenciar issues: `Resolve #123` ou `Relacionado a #456`

#### Exemplos de Commits Profissionais

**Commit simples**:
```
fix(banco): corrigir normalização de período nas consultas PMPV
```

**Commit com corpo**:
```
feat(etl): adicionar validação de qualidade para registros de penalidade

- Integrar framework de validação automática nos dados de entrada
- Validar formato, faixas numéricas e integridade referencial
- Cobrir cenários de período curto (Dez/25) e longo (Dez/2025)

Resolve #89
```

**Commit de refatoração**:
```
refactor(servicos): extrair lógica de normalização de períodos para módulo comum

- Mover normalizar_periodo() e variantes_periodo() para Src/common/periodos.py
- Atualizar database.py e excel_final_destino.py para usar módulo compartilhado
- Eliminar duplicação de lógica entre 4 módulos
```

**Commit de testes**:
```
test(banco): adicionar testes para exclusão completa de período

- Testar remoção de variantes legadas (Dez/25, DEZ/25, Dez/2025)
- Testar exclusão em cascata nas tabelas pmpv, auditoria, consolidação
- Validar que períodos não relacionados permanecem intactos
```

### Fase 4: Commit e Push

1. **Commit**: `git commit -m "<mensagem gerada>"`
   - Se o corpo for necessário, usar formato multi-linha com `-m` separados
2. **Push**: `git push -u origin <branch-atual>`
3. **Verificação**: Confirmar sucesso e exibir hash do commit

### Fase 5: Pull Request (apenas com `/push+pr`)

1. Detectar plataforma (GitHub/GitLab)
2. Gerar PR com:
   - **Título**: Reutilizar título do commit em português
   - **Descrição**: Popular com corpo do commit + checklist de revisão
   - **Labels**: Por tipo e escopo (ex: `melhoria`, `correção`, `backend`)
3. Exibir link do PR criado

## Relatório Final

Sempre exibir ao final:

```
═══════════════════════════════════════════
  Push Concluído
───────────────────────────────────────────
  Branch:       <nome-da-branch>
  Commit:       <hash-abreviado>
  Mensagem:     <tipo(escopo): título>
  Alterações:   <N> arquivos (+X, -Y linhas)
  Remote:       origin
  Status:       Enviado com sucesso
───────────────────────────────────────────
  PR: <link> (se /push+pr)
═══════════════════════════════════════════
```

## Proteções de Segurança

- **BLOQUEAR** se houver conflitos de merge não resolvidos
- **BLOQUEAR** se a mensagem de commit for genérica ou vazia
- **ALERTAR** antes de push em branches protegidas (main/master)
- **ALERTAR** se detectar force-push necessário
- **ALERTAR** se houver arquivos binários sendo commitados
- **CONFIRMAR** push bem-sucedido antes de reportar conclusão

## Execução Não-Interativa

- Não fazer perguntas adicionais — usar padrões sensatos
- Inferir tipo e escopo automaticamente a partir dos arquivos alterados
- Assumir que o usuário quer commitar **todas** as alterações staged
- Registrar todas as decisões no relatório final
- Se houver múltiplos commits lógicos distintos, fazer UM commit coeso que cubra tudo
