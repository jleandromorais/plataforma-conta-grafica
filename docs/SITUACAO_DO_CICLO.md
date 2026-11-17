# Situação do ciclo (`GET /api/ciclo/situacao`)

Só lê. Serviço: `Src/Services/tarifa/servicos_ciclo.py`. Não faz conta nova: usa a prévia da cascata
(`ServicosCascata.previa`), o VP e o SCG gravados e a SELIC do Banco Central.

## Os 5 passos de um trimestre civil T (ex.: Jul–Set/2026)

| # | chave | pronto quando | bloqueado por |
|---|---|---|---|
| 1 | `pmpv_anterior` | VP dos 3 meses de T gravado | (nunca; vira `falta`) |
| 2 | `pasta_scg` | SCG dos 3 meses de T gravado | (nunca; vira `falta`) |
| 3 | `sr` | SELIC fechada e SR gravado igual ao recalculado | SELIC aberta/sem publicação, ou passo 1 ou 2 incompleto |
| 4 | `pr_pv` | PR e PV do trimestre do ciclo seguinte gravados | SR não gravado, ou PMPV novo ausente |
| 5 | `tarifa_media` | PV gravado (só leitura; a conta e o fechamento ficam no PMPV) | PV não gravado |

Estados: `pronto`, `atencao` (calculado, falta aprovar ou o gravado difere), `falta` (o analista precisa
fazer algo), `bloqueado` (depende de outro passo ou de uma data). O SR **não** exige o PMPV seguinte.

## Quando a SELIC "fechou"

Regra nova (só na situação): `hoje > último dia do trimestre` **e** a série do Banco Central (SGS 11) traz os
3 meses **e** uma data igual ou posterior ao **último dia útil** do trimestre (seg–sex).
`libera_em` é uma **estimativa**: o 1º dia útil depois do fim do trimestre.

## Dúvidas abertas (precisam de confirmação)

1. **Publicação do Banco Central:** não verificamos em quantos dias úteis depois do fim do trimestre a
   série 11 passa a trazer o último dia. `libera_em` assume o dia seguinte; o estado `aguardando_publicacao`
   cobre a diferença com os dados reais.
2. **Feriados:** o "último dia útil" só considera fim de semana. Se a série do BC não traz uma data de feriado
   que caia no último dia (ex.: 31/12), a situação ficaria em `aguardando_publicacao` para sempre.
   Conferir com a série real em 31/12/2026 e, se for o caso, aceitar o dia útil anterior nessa data.
3. **Fora da situação:** `POST /cascata/aplicar` e a proposta do SR ainda usam a regra antiga
   (`hoje > fim do trimestre`, em `selic_do_trimestre`). Levar a nova regra para lá é decisão do Leandro,
   porque pode recusar um SR que hoje grava.
4. **SCG divergente da soma dos módulos** (caso de Jul): o passo 2 só confere se o SCG existe; não compara.
