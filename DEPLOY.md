# Deploy do back-end na nuvem

A API roda numa imagem Docker (`Dockerfile`) com **Tesseract em português**, que lê os PDFs
escaneados. O banco SQLite fica num **disco persistente** montado em `/data`.

## Variáveis de ambiente

| Variável | Valor | Obrigatória |
|---|---|---|
| `JWT_SECRET` | texto longo e aleatório (ex.: `openssl rand -hex 32`) | sim |
| `CORS_ORIGINS` | URL do front, ex.: `https://seu-front.vercel.app` (várias, separadas por vírgula) | sim |
| `PERMITIR_CADASTRO` | `0` fecha o auto-cadastro (crie as contas antes) | recomendada |
| `JWT_EXPIRA_HORAS` | validade do login (padrão 12) | não |
| `PLATAFORMA_DB` | já vem `/data/pmpv_data.db` na imagem | não |
| `PORT` | a plataforma costuma definir sozinha | não |

## Passo a passo (Render, Railway, Fly.io ou outro com Docker)

1. Crie um serviço a partir deste repositório, usando o **Dockerfile** da raiz.
2. Anexe um **disco/volume persistente** com ponto de montagem **`/data`**.
   Sem ele o banco some a cada novo deploy.
3. Defina as variáveis acima.
4. Suba. Na primeira vez o banco é criado vazio em `/data/pmpv_data.db`.
5. Teste: `https://SEU-BACK/api/health` deve responder `{"status":"ok"}`.
6. No front (Vercel), defina `VITE_API_URL=https://SEU-BACK/api` e faça um novo deploy.

## Levar os dados que você já tem

O banco não vai pelo git (`*.db` é ignorado). Para usar o seu `pmpv_data.db` já preenchido, copie-o
para o disco do servidor como `/data/pmpv_data.db` **antes** do primeiro uso (pelo shell/SSH da
plataforma), ou comece vazio e recalcule os meses pela tela.

## Cuidados

- O banco tem dados da empresa e a API só deve ser acessada com login. Defina `JWT_SECRET` e, depois
  de criar as contas, `PERMITIR_CADASTRO=0`.
- Use **uma instância só**: o SQLite não é feito para vários servidores gravando ao mesmo tempo.
- Sem o Tesseract, PDFs escaneados voltam sem valores. Esta imagem já o instala.
