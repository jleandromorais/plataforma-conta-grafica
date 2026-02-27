# 📊 Plataforma Conta Gráfica (SCG)

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![CustomTkinter](https://img.shields.io/badge/Interface-CustomTkinter-2ea44f?style=for-the-badge)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite)
![Pandas](https://img.shields.io/badge/Data-Pandas-150458?style=for-the-badge&logo=pandas)
![Pytest](https://img.shields.io/badge/Tests-Pytest-E11210?style=for-the-badge&logo=pytest)

## 📖 Sobre o Projeto

A **Plataforma Conta Gráfica** é um sistema desktop desenvolvido em Python para gestão, cálculo e consolidação de indicadores financeiros e faturas. O objetivo principal do software é automatizar o cálculo do **SCG (Sistema de Conta Gráfica)** e do **SR (Saldo Remanescente)**, oferecendo uma interface gráfica moderna e intuitiva.

Este sistema substitui processos manuais complexos por um fluxo de trabalho automatizado, integrando leitura de ficheiros Excel, armazenamento persistente em base de dados e validação de cálculos rigorosos.

## ✨ Principais Funcionalidades

O sistema está dividido em módulos independentes que convergem no Dashboard principal:

* **📈 Dashboard Central:** Visão geral e navegação entre os vários submódulos.
* **💼 Módulo SCG (Consolidação):** Calcula a métrica central através da fórmula `SCG = RPV × (CGR + CGF) + RET + RP`.
* **📊 Módulo SR (Saldo Remanescente):** Calcula as diferenças de volume faturado através da fórmula `SR = (VP - VF) × PR`.
* **📑 Módulos Base:**
    * **PMPV:** Preço Médio Ponderado de Venda.
    * **CGR & CGF:** Auditoria XML e Volumes Faturados.
    * **RPV & RET:** Requisição de Pequeno Valor e Encargos.
    * **RP:** Conciliação.
* **📥 Importação de Dados:** Processamento automatizado de dados provenientes de planilhas Excel (`pandas`).
* **🗄️ Base de Dados Embutida:** Persistência de dados local segura com `SQLite`.
* **🔄 Modos de Operação:** Permite ao utilizador alternar entre o modo Automático (dados do banco) e Manual (edição direta).

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** [Python 3.10+](https://www.python.org/)
* **Interface Gráfica (GUI):** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (tema escuro, design moderno).
* **Manipulação de Dados:** [Pandas](https://pandas.pydata.org/) e `openpyxl`.
* **Base de Dados:** `SQLite3` (nativo do Python).
* **Testes Automáticos:** `Pytest`.

## 📂 Arquitetura e Estrutura de Ficheiros

O projeto foi construído seguindo boas práticas de modularização, separando a interface (UI), a lógica de negócio e o acesso aos dados:

```text
plataforma-conta-grafica/
├── Src/
│   ├── Database/
│   │   └── database.py          # Camada de acesso à BD (SQLite)
│   └── Modules/
│       ├── excel_handler.py     # Lógica de extração e tratamento de Excel
│       ├── modulo_scg.py        # Módulo de Consolidação (UI + Lógica)
│       ├── modulo_sr.py         # Módulo de Saldo Remanescente
│       ├── modulo_pmpv.py       # ... (outros módulos de negócio)
│       └── ...
├── tests/                       # Suite de testes automatizados (Pytest)
│   ├── test_database.py
│   ├── test_excel_handler.py
│   └── test_modulo_*.py
├── main_dashboard.py            # Ponto de entrada (Entrypoint) e Menu Principal
├── requirements.txt             # Dependências do projeto
├── pytest.ini                   # Configurações de testes
└── README.md                    # Documentação do projeto
🚀 Como Instalar e Executar
Siga os passos abaixo para correr o projeto na sua máquina local.

Pré-requisitos
Ter o Python instalado (versão 3.10 ou superior).

Recomenda-se a utilização de um ambiente virtual (venv).

Passos de Instalação
Clone o repositório:

Bash
git clone [https://github.com/seu-usuario/plataforma-conta-grafica.git](https://github.com/seu-usuario/plataforma-conta-grafica.git)
cd plataforma-conta-grafica
Crie e ative um ambiente virtual (opcional, mas recomendado):

Bash
# Em Windows:
python -m venv venv
venv\Scripts\activate

# Em Linux/Mac:
python3 -m venv venv
source venv/bin/activate
Instale as dependências:

Bash
pip install -r requirements.txt
Inicie a aplicação:

Bash
python main_dashboard.py
🧪 Execução dos Testes
A qualidade do software é garantida através de uma suite robusta de testes unitários e de integração. Para executar todos os testes, certifique-se de que o pytest está instalado e corra:

Bash
pytest
Nota: A configuração do Pytest já se encontra otimizada no ficheiro pytest.ini para uma leitura clara dos resultados.

🤝 Contribuições e Manutenção
Desenvolvido com foco em código limpo, componentização Orientada a Objetos (Classes) e fácil escalabilidade. Qualquer dúvida ou sugestão, por favor, abra uma Issue no repositório.


---

### 📝 Instruções de Implementação

1. Abre o teu editor de código (VS Code, etc.).
2. Substitui o conteúdo atual do teu ficheiro `README.md` (ou `README_TESTES.md` caso queiras unificar a informação) por este código que forneci.
3. Repara que no bloco de instalação eu coloquei um link de clonagem de exemplo (`https://github.com/seu-usuario/plataforma-conta-grafica.git`). **Lembra-te de alterar "seu-usuario" para o teu nome de utilizador real do GitHub.**

### 🎓 Dica Educativa
Escrever um bom README faz parte do trabalho de um bom Programador Sênior. Ele ajuda a documentar para outros (e para ti mesmo no futuro) como a arquitetura do teu sistema funciona. Como separaste brilhantemente as funções da base de dados (`database.py`), do processamento de Excel (`excel_handler.py`) e das janelas de visualização (os módulos), destacar essa organização na secção **"Arquitetura"** vai impressionar quem ler o teu repositório!

O que achaste do visual e da organização do texto? Se quiseres alterar ou acrescentar a
