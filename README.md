# Plataforma Conta Gráfica

Sistema desktop e backend de apoio para apuração da Conta Gráfica, análise fiscal e consolidação operacional em um único Excel final.

O projeto combina interface local em Python com módulos especializados para cálculo, auditoria, leitura de arquivos e consolidação de resultados em banco SQLite e relatórios Excel.

## Visão Geral

Na prática, a aplicação permite:

- calcular PMPV trimestral com volumes e preços por empresa;
- importar memória de cálculo e salvar sessões PMPV;
- auditar NF-e e CT-e por XML e, quando necessário, por PDF/OCR;
- processar RET e Conciliação RP a partir de PDFs;
- apurar CGF, RPV, SR e SCG;
- consolidar tudo no Módulo 9, gerando um Excel final geral.

## Módulos da Aplicação

Os módulos principais disponíveis na interface estão em [Src/main_dashboard.py](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/Src/main_dashboard.py).

- `1. PMPV`: cálculo de PMPV, volume prospectivo, preço final e salvamento de sessões.
- `Conciliação RP`: leitura de PDFs de receita e despesa para apuração do saldo RP.
- `RET`: processamento de encargos e documentos vinculados ao RET.
- `Auditoria XML`: apuração de CGR a partir de XML e PDF/OCR.
- `CGF`: consolidação de volumes faturados, cancelados, devolvidos e consumo próprio.
- `RPV`: cálculo de `CGR - CGF`.
- `SR`: cálculo de `(Volume Prospectivo - VF) × PR`.
- `SCG`: consolidação final com `RPV + RET + RP`.
- `Módulo 9`: geração do Excel final consolidado.

## Como o Módulo 9 Funciona

O Excel final consolidado é gerado por [Src/infrastructure/exporters/excel_consolidado.py](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/Src/infrastructure/exporters/excel_consolidado.py).

Fluxo atual:

1. Cada módulo salva seus dados no banco local `pmpv_data.db`.
2. O botão `Adicionar ao Excel Final (Módulo 9)` salva ou atualiza os dados analisados do módulo atual.
3. O sistema pergunta qual sessão/arquivo do Excel final deve ser usada.
4. O relatório consolidado é gerado a partir do banco, com todos os dados já analisados.

Importante:

- o Excel final é geral por padrão;
- a sessão ativa do Módulo 9 pode ser reutilizada entre módulos;
- o PMPV salva sessão própria antes de entrar no consolidado;
- CGF, RET, Auditoria, RP, SR, RPV e SCG também entram no mesmo fluxo.

## Estrutura do Repositório

```text
plataforma-conta-grafica/
├── Src/
│   ├── application/         # Casos de uso
│   ├── common/              # Helpers utilitários
│   ├── config/              # Tema e configurações de UI
│   ├── Database/            # Banco SQLite e persistência base
│   ├── domain/              # Portas e contratos
│   ├── infrastructure/      # Exportadores, OCR, repositórios
│   ├── Services/            # Regras de negócio por módulo
│   ├── Views/               # Telas da aplicação
│   └── main_dashboard.py    # Dashboard principal
├── backend/                 # ETL, Airflow, DQ, monitoramento e reporting
├── tests/                   # Testes automatizados
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── start.py
└── README.md
```

## Requisitos

- Python 3.10 ou superior
- Windows é o ambiente principal de uso
- Docker Desktop é opcional para o backend com Airflow

Dependendo do ambiente local, a interface desktop também pode exigir bibliotecas visuais já utilizadas pelo projeto, como `customtkinter` e `Pillow`.

## Instalação Local

### PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se houver uso de variáveis locais, copie também o arquivo de ambiente quando necessário:

```powershell
Copy-Item .env.example .env
```

## Execução

### Interface Desktop

Para abrir a aplicação principal:

```powershell
python Src/main_dashboard.py
```

### Inicialização da Stack com Docker

O script [start.py](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/start.py) automatiza a subida do ambiente com Docker Compose:

```powershell
python start.py
```

Ou, manualmente:

```powershell
docker-compose up -d
```

Airflow Web UI:

- URL: http://localhost:8080
- Usuário: `airflow`
- Senha: `airflow`

## Fluxo Recomendado de Uso

Quando a intenção for gerar o Excel final consolidado, o fluxo sugerido é:

1. Processar os módulos que interessam para o período.
2. Salvar os dados em cada módulo ou usar o botão `Adicionar ao Excel Final (Módulo 9)`.
3. Reutilizar a mesma sessão do Excel final quando solicitado.
4. Ao final, abrir o Módulo 9 ou qualquer botão de adicionar e gerar o arquivo geral consolidado.

Exemplo prático:

1. PMPV: calcular, importar memória se necessário e salvar sessão.
2. Auditoria XML: calcular CGR e salvar.
3. CGF: calcular volume final e salvar.
4. RET e Conciliação: processar e salvar.
5. SCG: revisar consolidação.
6. Gerar o Excel final geral.

## Banco de Dados Local

O projeto utiliza SQLite local para persistência operacional.

Arquivos principais persistidos:

- `pmpv_data.db`: base principal da aplicação.
- tabelas de sessões PMPV, consolidação, SR, CGF e itens detalhados.

O banco principal é usado como fonte de verdade para o Excel consolidado.

## Testes

Para rodar a suíte de testes:

```powershell
python -m pytest
```

O projeto já possui configuração em [pytest.ini](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/pytest.ini).

## Comandos Úteis

Há uma lista adicional em [COMANDOS.md](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/COMANDOS.md) com exemplos de:

- subida da stack;
- verificação de containers;
- logs do Airflow;
- troubleshooting;
- comandos de teste.

## Observações Importantes

- Não commitar `.env` real.
- Não commitar bancos locais, relatórios gerados e massas grandes de dados.
- OCR e leitura por Gemini dependem de configuração e disponibilidade do ambiente.
- Parte do backend foi pensada para uso recorrente com Airflow, mas a aplicação desktop pode ser usada de forma independente.

## Pontos de Entrada Relevantes

- Dashboard principal: [Src/main_dashboard.py](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/Src/main_dashboard.py)
- Banco local: [Src/Database/database.py](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/Src/Database/database.py)
- Exportador Excel final: [Src/infrastructure/exporters/excel_consolidado.py](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/Src/infrastructure/exporters/excel_consolidado.py)
- Inicialização Docker: [start.py](c:/Users/jose.demorais/Downloads/Plataforma/plataforma-conta-grafica/start.py)

## Licença

Defina a licença do projeto antes de distribuição externa. Se a intenção for publicação aberta, uma opção comum é MIT.
