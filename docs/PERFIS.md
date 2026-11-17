# Perfis de acesso e "quem fez" na trilha

Código: `Src/api/perfis.py` (a matriz e a conferência), `Src/api/auth.py` (perfis guardados no banco),
`Src/api/routers/usuarios.py` (administrador troca perfis). Testes: `tests/test_perfis.py`.

## Ligar e desligar: `PERFIS_ATIVOS`

| Valor | O que acontece |
|---|---|
| `0` ou ausente (padrão) | **Nada muda.** Todo usuário logado pode tudo, como antes. A trilha já anota quem fez (nome, e-mail, perfil, ação) e o motivo, se vier. |
| `1` | A matriz abaixo vale. Quem não tem o perfil recebe **403** com uma frase dizendo quem pode. As escolhas do analista (SCG gravado × soma, SR anterior, SELIC manual, MB) exigem o campo `motivo` (sem ele, 422). |

Para ligar: no Railway, crie a variável `PERFIS_ATIVOS=1` e reinicie o serviço. Para desligar (volta ao
comportamento antigo na hora): `PERFIS_ATIVOS=0` ou apague a variável.

### Antes de ligar (para ninguém ficar trancado para fora)
1. **Contas que já existem viram `administrador` sozinhas** na primeira vez que o servidor sobe com esta versão
   (migração de uma vez só). Confira em `GET /api/usuarios` (só administrador).
2. Dê os perfis certos a cada pessoa: `PUT /api/usuarios/{id}/perfis` com `{"perfis": ["operador", "aprovador"]}`.
   Uma pessoa pode ter mais de um perfil. Lista vazia = sem acesso (com `PERFIS_ATIVOS=1`).
3. O sistema **não deixa tirar o último administrador**.
4. Conta nova nasce **`consulta`**. A primeira conta de uma instalação sem nenhum administrador nasce `administrador`.
5. O perfil é lido do banco **a cada requisição** (não vai no token): trocar o perfil vale na hora, sem novo login.
6. `GET/PUT /api/usuarios` exigem `administrador` **mesmo com `PERFIS_ATIVOS=0`** (rotas novas).
7. Feche o auto-cadastro no Railway: `PERMITIR_CADASTRO=0` (o padrão é aberto).

## Perfis

| Perfil | Para quê |
|---|---|
| `consulta` | Só lê. |
| `operador` | Processa a pasta e grava os módulos (CGR, CGF, RET, RP, SCG, PMPV). |
| `aprovador` | Aprova SR, PR e PV. |
| `analista` | Revisa; decide SCG gravado × soma, SR anterior, SELIC manual e MB (sempre com motivo); também aprova. |
| `administrador` | Usuários e perfis; apaga PR, período e SCG; limpa dados de teste; repara o histórico do SCG. |

## Matriz (S = pode; N = recusa com 403 quando `PERFIS_ATIVOS=1`)

| Ação (rotas) | consulta | operador | aprovador | analista | administrador |
|---|---|---|---|---|---|
| Ver telas, provas reais, trilha (todo `GET`) e cálculos de prévia (`/sr/calcular`, `/sr/trimestre/proposta`, `/pr/apurar`...) | S | S | S | S | S |
| Processar a pasta e gravar módulo (`/auditoria`, `/cgf`, `/ret`, `/conciliacao`, `/rpv`, `/scg/salvar`, `/pmpv/salvar`, Excel Final...) | N | S | N | S | S |
| Escolher SCG gravado × soma (`escolha` em `/scg/salvar`), SR anterior diferente do gravado ou `selic_manual` (`/sr/trimestre/salvar`), MB (`/pmpv/margem-regulatoria`), **com `motivo`** | N | N | N | S | N |
| Aprovar SR, PR e PV (`/sr/trimestre/salvar`, `/pr/salvar`, `/pv/salvar`, `/pv/trimestre/salvar`, `/cascata/aplicar`) | N | N | S | S | N |
| Revisar e fechar o trimestre | N | N | N | S | N (**rota ainda não existe**) |
| Apagar PR, período ou SCG (`DELETE /pr`, `/periodos/{nome}`, `/scg`) | N | N | N | N | S |
| Reparar histórico do SCG (`/scg/reparar-historico`) | N | N | N | N (a Amanda marcou "condicional") | S |
| Relatório oficial do trimestre (`/nota-tecnica/gerar`, `/relatorio-trimestral/gerar`) | N | N | N (condicional) | S | S |
| Usuários e perfis (`/usuarios`) | N | N | N | N | S |

Onde há "condicional" na matriz da Amanda, o código recusa até o analista humano decidir.
Toda rota que muda algo precisa estar em `REGRAS` (`Src/api/perfis.py`): o teste
`test_toda_rota_que_muda_algo_esta_na_tabela_de_regras` falha se uma rota nova ficar de fora.

## O que a trilha registra (`GET /api/trilha`)

Colunas novas em `historico_alteracoes`, todas opcionais: `usuario_id`, `usuario_nome`, `usuario_email`,
`perfil`, `acao`, `motivo`. Ficam vazias nas linhas antigas e nas gravações que não vieram da API com login
(app desktop, scripts). `acao` é o nome da regra (`salvar_modulo`, `aprovar_sr`, `aprovar_pr`, `aprovar_pv`,
`aprovar_cascata`, `escolher`, `apagar_pr`, `apagar_scg`, `apagar_periodo`...). Os apagamentos de `DELETE /scg` e
`DELETE /periodos` agora entram na trilha (valor antigo → vazio, origem `apagar`), e `DELETE /pr`, `/scg` e
`/periodos` aceitam `?motivo=` opcional.

## Fora desta entrega (decisões e telas pendentes)
- `aprovacoes`, `pacote_id`, `regra_versao` e o pacote de aprovação congelado (seção da Amanda).
- Marca "mesma pessoa processou e aprovou" e a revisão do analista com "conferido".
- A tela do site para escolher perfis (por enquanto, `PUT /api/usuarios/{id}/perfis`).
