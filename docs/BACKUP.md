# Backup do banco SQLite

Script: [`scripts/backup_banco.py`](../scripts/backup_banco.py). Testes: `tests/test_backup.py`.

## O que ele faz

- **Cria** uma cópia consistente com a API de backup do SQLite (segura mesmo com o servidor aberto; copiar o `.db` na mão não é).
  A origem nunca é alterada (abre em modo só leitura).
- **Nome com data e hora:** `pmpv_data_AAAAMMDD_HHMMSS.db`, em `backups/` (ou na pasta de `--pasta` / `PLATAFORMA_BACKUP_DIR`).
- **Valida** a cópia: `PRAGMA integrity_check` e número de tabelas igual ao da origem. Se falhar, apaga a cópia ruim e **não** aplica a retenção.
- **Retenção:** guarda as 30 mais novas (`--manter N` ou `PLATAFORMA_BACKUP_MANTER`). Só apaga arquivos com o nome acima; backups manuais com outros nomes ficam intocados.
- **Origem:** a mesma regra do resto do código: `PLATAFORMA_DB`, depois `caminho_banco.txt`, depois `pmpv_data.db`.
- **Restaura** em um arquivo de destino. Recusa sobrescrever arquivo existente sem `--confirmo-sobrescrever`, e nesse caso guarda antes o que havia como `<destino>.antes_da_restauracao_<data>`.

## Comandos

```
python scripts/backup_banco.py criar
python scripts/backup_banco.py validar backups/pmpv_data_20261117_080000.db
python scripts/backup_banco.py listar
python scripts/backup_banco.py restaurar backups/pmpv_data_20261117_080000.db --destino C:\temp\teste.db
```

## Testar a restauração (faça antes de confiar no backup)

1. `restaurar` para um arquivo novo em outra pasta (como acima).
2. Aponte uma API de teste para ele: `PLATAFORMA_DB=C:\temp\teste.db uvicorn Src.api.main:app --port 8081` e abra o Painel do Ciclo.
3. Só restaure por cima do banco real com o servidor **parado** e com `--confirmo-sobrescrever`.

## Agendar (nada disso foi executado em produção)

**Atenção ao limite do Railway:** um volume só pode ser montado em um serviço. Um cron em outro serviço **não enxerga** `/data`, e uma cópia gravada no mesmo volume não protege contra perda do volume. Por isso o backup útil precisa sair do servidor.

Opções, da mais simples para a mais completa:

1. **Pela máquina da empresa (sem mudar o servidor):** tarefa agendada do Windows que baixa o banco com a CLI do Railway e valida. Rascunho (ajustar projeto/serviço):
   `railway ssh -- python scripts/backup_banco.py criar --pasta /data/backups` e depois baixar o arquivo mais novo de `/data/backups` para a pasta da empresa. Exige a CLI instalada e logada.
2. **Cron dentro do serviço da API:** o Railway permite "Cron Schedule" apenas em serviço próprio, que não vê o volume. Para esse caminho funcionar seria preciso um serviço de backup que tenha acesso ao banco por rede (hoje não existe), ou uma rota protegida de download. **Decisão pendente do Leandro** (ver abaixo).
3. **Bucket na nuvem (S3, R2, Backblaze):** o mesmo script, seguido de `aws s3 cp` (ou `rclone copy`) do arquivo gerado. Também exige decidir onde guardar e criar credenciais.

Agende diariamente (ex.: 02:00). Expressão de cron: `0 2 * * *`.

### O que o Dockerfile precisa

O `Dockerfile` copia só `Src/` e `seed/`; foi adicionada a linha `COPY scripts/backup_banco.py ./scripts/backup_banco.py` para o script existir na imagem (vale a partir do próximo deploy).

## Decisões em aberto (Leandro)

- Onde guardar a cópia fora do Railway (bucket, pasta da empresa).
- Se o backup será puxado de fora (opção 1) ou se vale uma rota de download protegida por perfil.
- Avaliar Postgres no Railway (backup gerenciado), cartão `[Banco] backup e avaliar Postgres`.

## Cuidados

- `backups/` está no `.gitignore`: as cópias têm dados da empresa e **nunca** devem ir para o repositório público.
- Teste a restauração periodicamente, não só a criação.
