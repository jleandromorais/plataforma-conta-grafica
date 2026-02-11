# 📊 Plataforma Conta Gráfica

> Sistema integrado de gestão financeira com cálculo PMPV trimestral e conciliação de documentos.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1f538d?style=flat)
![Status](https://img.shields.io/badge/status-em%20construção-yellow?style=flat)

---

## 🚧 Em construção

Este projeto ainda está em desenvolvimento. No momento **falta a parte de somar o PR** (e possíveis ajustes em outros módulos). Contribuições e sugestões são bem-vindas.

---

## ✨ O que já tem

| Módulo | Descrição |
|--------|-----------|
| **🏠 Dashboard** | Tela inicial com atalhos para PMPV e Conciliação |
| **📊 Gestão PMPV** | Calculadora trimestral: empresas (PETROBRAS, GALP, etc.), molécula, transporte, logística, QDC, conta gráfica |
| **📄 Conciliação PDF** | Leitura de PDFs (texto e OCR com Tesseract), extração de valores e exportação para Excel |
| **💾 Banco de dados** | Salvamento de sessões PMPV e resultados |
| **📁 Exportação Excel** | Geração de planilhas com dados do trimestre |

---

## 🛠️ Tecnologias

- **Python 3**
- **CustomTkinter** – interface moderna (tema escuro)
- **SQLite** – persistência de dados
- **openpyxl** – geração de Excel
- **pdfplumber** – extração de texto de PDF
- **pytesseract** – OCR em PDFs escaneados (opcional)

---

## 📦 Como rodar

### 1. Clonar e entrar na pasta

```bash
git clone https://github.com/SEU_USUARIO/plataforma-conta-grafica.git
cd plataforma-conta-grafica
```

### 2. Criar ambiente virtual (recomendado)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependências

```bash
pip install customtkinter openpyxl pdfplumber pytesseract pillow
```

> **OCR:** Para usar leitura de PDFs escaneados, instale o [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (o projeto usa o caminho padrão em `C:\Program Files\Tesseract-OCR`).

### 4. Executar

```bash
python main_dashboard.py
```

---

## 📁 Estrutura do projeto

```
plataforma-conta-grafica/
├── main_dashboard.py    # Janela principal e menu
├── modulo_pmpv.py      # Calculadora PMPV trimestral
├── modulo_concilia.py  # Conciliação de PDFs (OCR + Excel)
├── database.py         # Sessões e resultados (SQLite)
├── excel_handler.py    # Exportação para Excel
├── pmpv_data.db        # Banco de dados (gerado ao usar)
└── README.md
```

---

## 📌 Próximos passos (roadmap)

- [ ] **Somar o PR** – implementar a soma do PR no fluxo da plataforma
- [ ] Ajustes e testes nos módulos atuais
- [ ] (Opcional) Melhorias de UX e relatórios

---

## 📄 Licença

Uso interno / em desenvolvimento. Ajuste conforme sua necessidade.

---

*Desenvolvido com Python e CustomTkinter.*
