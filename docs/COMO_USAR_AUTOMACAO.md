
# Guia de Automação — GraphAccount Pro

Este guia explica como configurar e rodar a automação do fechamento mensal
**sem abrir o app desktop**, com custo R$ 0,00.

---

## Como funciona

```
Todo dia 10 do mês às 08:00
          ↓
   pipeline.py roda sozinho
          ↓
   Lê os arquivos das pastas
   Processa todos os módulos
   Gera o Excel final
          ↓
   E-mail chega: "✅ Fechamento Mai/2026 gerado"
          ↓
   Analista abre só para conferir
```

O app desktop continua funcionando normalmente. Use-o quando:
- Receber e-mail de falha (`⛔ PIPELINE FALHOU`)
- Precisar corrigir um número manualmente
- Quiser conferir um detalhe específico

---

## Passo 1 — Organizar as pastas de entrada

Crie esta estrutura de pastas (os nomes podem ser configurados no `config.env`):

```
dados/entrada/
  ├── CGR/        ← XMLs das NF-e e CT-e (Auditoria)
  ├── RET/        ← PDFs de encargos de transporte
  ├── CGF/        ← Excels de volume faturado
  │   ├── arquivo_faturadas.xlsx
  │   ├── NF canceladas e denegadas.xlsx
  │   └── Volume Devolução.xlsx
  ├── RP/         ← PDFs de penalidades
  │   ├── Receita/   (ou arquivos com "RECEITA" no nome)
  │   └── Despesa/   (ou arquivos com "DESPESA" no nome)
  └── PMPV/       ← Excel de Memória de Cálculo
```

> **Dica:** todo mês, basta copiar os novos arquivos para as pastas.
> O pipeline detecta automaticamente pelo nome do arquivo.

---

## Passo 2 — Editar o config.env

Abra o arquivo `config.env` e ajuste:

```env
# Caminho da pasta com os dados (use \\ ou / no Windows)
PASTA_ENTRADA=C:\\dados\\SCG-2026

# Nome da empresa (aparece nos relatórios)
EMPRESA_PADRAO=COPERGÁS

# Valor da Conta Gráfica para o PMPV
PMPV_VALOR_CG=-0.0210
```

---

## Passo 3 — Configurar e-mail (opcional, gratuito)

Para receber alertas de sucesso/falha por e-mail:

1. Acesse [myaccount.google.com](https://myaccount.google.com) → **Segurança**
2. Ative **Verificação em 2 etapas**
3. Em Segurança → **Senhas de app** → crie uma senha para "GraphAccount"
4. Edite o `config.env`:

```env
EMAIL_REMETENTE=seu.email@gmail.com
EMAIL_SENHA_APP=xxxx xxxx xxxx xxxx
EMAIL_DESTINATARIO=analista@empresa.com
```

5. Teste a configuração:
```bash
python notificador.py
```

> Se receber o e-mail de teste, está funcionando.

---

## Passo 4 — Instalar o agendamento automático

Abra o terminal **como Administrador** (clique direito → Executar como admin):

```bash
# Instala: roda todo dia 10 às 08:00
python instalar_agendamento.py

# Personalizar dia e hora:
python instalar_agendamento.py --dia 5 --hora 07:30

# Verificar se foi criado:
python instalar_agendamento.py --status

# Testar sem processar dados:
python instalar_agendamento.py --testar
```

Pronto. O Task Scheduler do Windows vai rodar o pipeline automaticamente.

---

## Como rodar manualmente (quando precisar)

```bash
# Mês atual
python pipeline.py

# Mês específico
python pipeline.py --periodo Mai/2026

# Pasta específica
python pipeline.py --periodo Mai/2026 --pasta C:\dados\SCG-2026

# Validar pastas sem processar (não toca no banco)
python pipeline.py --dry-run
```

---

## Entendendo os logs

Tudo que o pipeline faz é registrado em `logs/app.log`. Quando algo der errado:

```
[Auditoria] OK — 47 documentos | CGR = R$ 1.234.567,89
[RET] OK — 12 itens | RET = R$ 45.678,90
[CGF] OK — VF = 42.801.034,8661 m³
[Conciliação] OK — RP = R$ -12.345,67
[PMPV] OK — PMPV = R$ 2,1154/m³
[SCG] OK — SCG = R$ 987.654,32
[Excel] Gerado: saida/Relatorio_ContaGrafica_Mai-2026.xlsx
```

Cada linha mostra o resultado da etapa.

> **Auditoria, RET, CGF e Conciliação são independentes**: se uma delas
> mostrar `FALHOU` (ex.: um PDF corrompido no RET), as outras continuam
> normalmente — o pipeline não para ali. Só ao final dessas quatro etapas
> (+ PMPV) é que o pipeline decide: se **todas** passaram, segue para
> Consolidação e Excel; se **alguma** falhou, ele para *antes* de gerar o
> SCG (que ficaria incompleto/errado) e manda **um único e-mail** listando
> todas as etapas que falharam naquela execução.

---

## Estrutura dos arquivos criados

```
plataforma-conta-grafica/
  ├── pipeline.py              ← Motor da automação (o coração)
  ├── notificador.py           ← Alertas por e-mail
  ├── instalar_agendamento.py  ← Configura o Task Scheduler
  ├── config.env               ← Suas configurações (NÃO commitar no Git)
  ├── dados/
  │   └── entrada/             ← Arquivos de entrada (copie aqui todo mês)
  ├── saida/                   ← Excels gerados ficam aqui
  └── logs/
      └── app.log              ← Tudo registrado aqui
```

---

## Custo total: R$ 0,00

| Componente | Custo |
|---|---|
| Python + bibliotecas | Grátis (open-source) |
| Windows Task Scheduler | Grátis (nativo do Windows) |
| Gmail SMTP (e-mail) | Grátis |
| SQLite (banco) | Grátis |
| **Total** | **R$ 0,00** |

---

## Perguntas frequentes

**O pipeline falhou, o que faço?**
1. Leia o log: `logs/app.log`
2. Abra o app desktop
3. Processe a etapa com falha manualmente
4. Continue pelas etapas seguintes normalmente

**Posso rodar o pipeline mais de uma vez no mesmo mês?**
Sim. O pipeline é idempotente: rodar duas vezes com os mesmos dados
sobrescreve os resultados anteriores sem duplicar.

**E se a máquina estiver desligada no dia 10?**
O Task Scheduler não executa tarefas perdidas por padrão. Se a máquina
estava desligada, rode manualmente: `python pipeline.py --periodo Mai/2026`

**Como remover o agendamento?**
```bash
python instalar_agendamento.py --remover
```

**O app desktop ainda funciona depois de instalar isso?**
Sim. O pipeline e o app usam o mesmo banco de dados. Você pode abrir
o app a qualquer momento para conferir, corrigir ou fazer cálculos manuais.
