# ⚡ Plataforma Conta Gráfica | Hiper-Automação Regulatória

<div align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white">
  <img alt="RPA & Automação" src="https://img.shields.io/badge/RPA_%26_Automação-Eficiência_Extrema-FF4500?style=for-the-badge">
  <img alt="Clean Architecture" src="https://img.shields.io/badge/Clean_Architecture-SOLID-brightgreen?style=for-the-badge">
</div>

<br>

> **De 3 meses para 1 dia.** Como a engenharia de software transformou o processamento de dados do Setor de TI da Agência de Regulação de Pernambuco (ARPE).

---

## 🎯 O Impacto do Projeto (O Problema vs. A Solução)

A Agência lida com um volume colossal de cálculos regulatórios. O processo tradicional era um verdadeiro labirinto manual que envolvia a leitura humana de **milhares de ficheiros PDF** e o cruzamento denso de dados em **inúmeras folhas de cálculo Excel**. 

Este fluxo de trabalho manual demorava cerca de **3 meses** a ser concluído pela equipa.

Desenvolvi a **Plataforma Conta Gráfica** para erradicar essa ineficiência. Através da construção de um *pipeline* de dados robusto em Python e orquestração inteligente, o processo foi integralmente automatizado. **O tempo de execução foi reduzido de 90 dias para apenas 24 horas.**

---

## 🖥️ Interface Gráfica (Dashboard)

Para garantir que a equipa da agência conseguisse operar a automação com facilidade, desenvolvi uma interface gráfica fluida e intuitiva. Abaixo estão algumas capturas de ecrã dos principais módulos do sistema:

### 🏠 Tela Principal & Navegação
> *Visão geral da plataforma, permitindo o acesso rápido aos diferentes módulos de cálculo e auditoria.*

<img src="caminho/para/a/tua/imagem_dashboard.png" alt="Tela Principal do Dashboard" width="800">

### 📄 Módulo de Processamento (Ex: PMPV / OCR)
> *Interface onde o utilizador aciona a extração em lote dos ficheiros PDF e acompanha o progresso da automação em tempo real.*

<img src="caminho/para/a/tua/imagem_processamento.png" alt="Tela de Processamento PMPV" width="800">

### 📊 Módulo de Auditoria e Conciliação
> *Ambiente dedicado à consolidação dos dados, onde o sistema cruza as informações processadas com as folhas de cálculo Excel.*

<img src="caminho/para/a/tua/imagem_auditoria.png" alt="Tela de Auditoria e Conciliação" width="800">

---

## 🧠 Arquitetura e Engenharia em Python

Este não é apenas um "script de automação". O projeto foi rigorosamente desenhado em **Python**, adotando princípios de **Clean Architecture** e **SOLID**, garantindo que a aplicação é escalável, modular e fácil de manter.

A estrutura do domínio foi isolada da infraestrutura, permitindo uma separação clara de responsabilidades:

* **`/domain` & `/application`:** O coração do sistema. Aqui residem os *Use Cases* e as lógicas de cálculo regulatório puro.
* **`/infrastructure` & `/infra`:** Os motores de I/O. Inclui módulos avançados de **OCR** para extração de dados não estruturados de PDFs e repositórios **SQLite**.
* **`/Services`:** A camada de orquestração que gere fluxos de consolidação e auditoria de contas.
* **`/Views`:** Componentes visuais do Dashboard mostrados acima.

---

## ⚙️ Funcionalidades Core (Data Pipeline & RPA)

- [x] **Motor de OCR em Massa:** Varredura e *parsing* inteligente de PDFs.
- [x] **Processamento de Excel a Alta Velocidade:** Leitura, cruzamento e escrita sem margem de erro.
- [x] **Módulos de Auditoria:** Serviços automatizados que validam a consistência dos dados.
- [x] **Testabilidade:** Suíte de testes automatizados com `pytest`.

---

## 🏗️ Estrutura do Projeto

O projeto está organizado por camadas, com foco absoluto na separação de responsabilidades:

```text
plataforma-conta-grafica/
├── Src/
│   ├── application/
│   │   └── use_cases/
│   │       └── pmpv_use_cases.py
│   ├── domain/
│   │   └── ports/
│   │       └── repositories.py
│   ├── infrastructure/
│   │   ├── repositories/
│   │   │   └── sqlite_repositories.py
│   │   └── exporters/
│   │       └── excel_handler_pmpv.py
│   ├── Database/
│   │   └── database.py
│   ├── Services/
│   │   ├── servicos_consolidacao.py
│   │   ├── servicos_pmpv.py
│   │   └── ...
│   ├── Views/
│   │   ├── tela_pmpv.py
│   │   ├── tela_scg.py
│   │   └── ...
│   ├── infra/
│   │   └── ocr_pdf.py
│   └── main_dashboard.py
├── tests/
│   ├── test_database.py
│   ├── test_excel_handler.py
│   ├── test_integracao.py
│   ├── test_servicos_consolidacao.py
│   └── test_pmpv_use_cases.py
├── main.py
├── requirements.txt
├── pytest.ini
└── README.md
🚀 Como Iniciar (Setup Local)
Pré-requisitos
Certifica-te de ter o Python 3.9+ instalado na tua máquina.

Instalação
Clonar o repositório:

Bash
git clone [https://github.com/teu-usuario/plataforma-conta-grafica.git](https://github.com/teu-usuario/plataforma-conta-grafica.git)
cd plataforma-conta-grafica
Criar um ambiente virtual isolado:

Bash
python -m venv venv
# Para ativar no Windows:
venv\Scripts\activate
# Para ativar no Linux/macOS:
source venv/bin/activate
Instalar as dependências do projeto:

Bash
pip install -r requirements.txt
Iniciar o Dashboard da Plataforma:

Bash
python main.py
