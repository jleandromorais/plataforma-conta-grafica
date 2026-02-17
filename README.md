# 🏦 Plataforma Conta Gráfica - Sistema Integrado

[![Tests](https://img.shields.io/badge/tests-39%20passing-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-56%25-yellow)]()
[![Python](https://img.shields.io/badge/python-3.14-blue)]()

Sistema integrado de gestão financeira com funcionalidades de cálculo PMPV (Preço Médio Ponderado de Venda), conciliação de PDFs e exportação para Excel.

## 📋 Índice

- [Funcionalidades](#funcionalidades)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Instalação](#instalação)
- [Como Usar](#como-usar)
- [Testes](#testes)
- [Documentação](#documentação)

## ✨ Funcionalidades

### 1. **Cálculo PMPV Trimestral**
- Gestão de contratos de gás por empresa
- Cálculo automático de preços médios
- Inclusão de conta gráfica
- Exportação para Excel com múltiplas abas
- Salvamento em banco de dados SQLite

### 2. **Conciliação de PDFs**
- Leitura automática de PDFs (texto digital + OCR)
- Extração inteligente de valores monetários
- Categorização de receitas e despesas
- Geração de relatório consolidado em Excel
- Interface gráfica moderna

### 3. **Auditoria XML (NF-e / CT-e)**
- Leitura recursiva de XMLs fiscais em múltiplas empresas
- Parse automático de NF-e e CT-e
- Comparação com planilha Excel de referência
- Detecção de divergências em valores e volumes
- Geração de relatório completo com status colorido

### 4. **Dashboard Principal**
- Interface centralizada
- Acesso rápido aos módulos
- Design moderno com CustomTkinter

## 📁 Estrutura do Projeto

```
plataforma-conta-grafica/
│
├── 📄 Módulos Principais
│   ├── main_dashboard.py          # Dashboard principal
│   ├── modulo_pmpv.py             # Módulo de cálculo PMPV
│   ├── modulo_concilia.py         # Módulo de conciliação PDF
│   ├── modulo_auditoria.py        # Módulo de auditoria XML (NF-e/CT-e)
│   ├── database.py                # Gerenciamento do banco de dados
│   └── excel_handler.py           # Exportação para Excel
│
├── 🧪 Testes (tests/)
│   ├── __init__.py
│   ├── test_database.py           # 8 testes de BD
│   ├── test_excel_handler.py      # 8 testes de Excel
│   ├── test_modulo_concilia.py    # 11 testes de conciliação
│   └── test_integracao.py         # 12 testes de integração
│
├── 📚 Documentação
│   ├── README.md                  # Este arquivo
│   ├── README_TESTES.md           # Guia completo de testes
│   ├── RESUMO_TESTES.md          # Resumo executivo
│   └── CHANGELOG.md              # Histórico de mudanças
│
├── ⚙️ Configuração
│   ├── requirements.txt           # Dependências Python
│   └── pytest.ini                # Configuração de testes
│
└── 📊 Relatórios
    └── htmlcov/                   # Cobertura de testes (HTML)
```

## 🚀 Instalação

### 1. Clonar/Baixar o Projeto
```bash
cd plataforma-conta-grafica
```

### 2. Instalar Dependências
```bash
pip install -r requirements.txt
```

**Dependências Principais:**
- `customtkinter` - Interface gráfica moderna
- `openpyxl` - Manipulação de Excel
- `pdfplumber` - Leitura de PDFs
- `pytesseract` - OCR (reconhecimento de texto)
- `Pillow` - Processamento de imagens

**Dependências de Teste:**
- `pytest` - Framework de testes
- `pytest-cov` - Cobertura de código
- `pytest-mock` - Mocking para testes

### 3. Configurar Tesseract OCR (Opcional)
Se for usar OCR para PDFs escaneados:
1. Baixe o Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
2. Instale em: `C:\Program Files\Tesseract-OCR`
3. O sistema detectará automaticamente

## 💻 Como Usar

### Iniciar o Sistema
```bash
python main_dashboard.py
```

### Módulo PMPV
1. No dashboard, clique em "📊 Gestão PMPV"
2. Configure o trimestre (mês inicial)
3. Preencha dados de cada empresa por mês
4. Adicione o valor da conta gráfica
5. Clique em "⚡ CALCULAR"
6. Exporte para Excel ou salve a sessão

### Módulo Conciliação PDF
1. No dashboard, clique em "📄 Conciliação PDF"
2. Selecione pasta de Receitas
3. Selecione pasta de Despesas
4. Clique em "⚡ PROCESSAR E CONCILIAR"
5. Aguarde o processamento
6. Excel será gerado automaticamente

### Módulo Auditoria XML
1. No dashboard, clique em "🔍 Auditoria XML"
2. Selecione a pasta PAI contendo subpastas de empresas
3. Marque as empresas que deseja auditar
4. Selecione o Excel de referência (com dados esperados)
5. Clique em "⚡ INICIAR AUDITORIA"
6. Gere o relatório em Excel com divergências identificadas

## 🧪 Testes

### Executar Todos os Testes
```bash
pytest
```

### Com Cobertura Detalhada
```bash
pytest --cov=. --cov-report=html
```
Abra `htmlcov/index.html` no navegador para ver o relatório visual.

### Executar Teste Específico
```bash
pytest tests/test_database.py -v
```

### Estatísticas de Testes
- ✅ **39 testes** criados
- ✅ **100% passando**
- ✅ **56% de cobertura total**
- ✅ **87-91% de cobertura** nos módulos principais

## 📚 Documentação

### Para Usuários
- **README.md** (este arquivo) - Visão geral do sistema
- **RESUMO_TESTES.md** - Resumo executivo das melhorias

### Para Desenvolvedores
- **README_TESTES.md** - Guia completo de testes
- **CHANGELOG.md** - Histórico detalhado de mudanças
- **Cobertura HTML** - `htmlcov/index.html`

## 🔧 Correções Recentes (v1.1.0)

### Problema: Arquivos com Mesmo Nome
**Resolvido! ✅**

O sistema agora:
- Gera nomes únicos com timestamp completo
- Detecta arquivos já abertos
- Adiciona numeração incremental automática (`_1`, `_2`, etc.)
- Fecha arquivos corretamente após salvar
- Nunca sobrescreve dados

**Exemplo:**
```
Relatorio_PMPV_20260212_143052.xlsx
Relatorio_PMPV_20260212_143052_1.xlsx  ← Se já existir
Conciliacao_Final_20260212_143055.xlsx
```

## 🎯 Próximas Melhorias

- [ ] Testes de interface gráfica
- [ ] Integração contínua (CI/CD)
- [ ] Testes de performance
- [ ] Exportação para PDF
- [ ] Gráficos e dashboards

## 📊 Qualidade de Código

| Métrica | Valor | Status |
|---------|-------|--------|
| **Testes** | 39 | ✅ |
| **Cobertura** | 56% | ✅ |
| **Módulo Database** | 87% | ✅ |
| **Módulo Excel** | 91% | ✅ |
| **Testes Passando** | 100% | ✅ |

## 🤝 Contribuindo

1. Execute os testes antes de fazer commit:
   ```bash
   pytest
   ```

2. Adicione testes para novos recursos:
   ```python
   # tests/test_nova_funcionalidade.py
   def test_minha_funcionalidade():
       assert funcao() == resultado_esperado
   ```

3. Mantenha cobertura > 80% nos novos módulos

## 📄 Licença

Este projeto é de uso interno.

## 📞 Suporte

Para dúvidas sobre:
- **Uso do sistema**: Consulte este README
- **Execução de testes**: Veja `README_TESTES.md`
- **Mudanças recentes**: Leia `CHANGELOG.md`
- **Resumo executivo**: Abra `RESUMO_TESTES.md`

---

**Versão:** 1.1.0  
**Data:** 12/02/2026  
**Status:** ✅ Produção  
**Qualidade:** ⭐⭐⭐⭐⭐ (Profissional)
