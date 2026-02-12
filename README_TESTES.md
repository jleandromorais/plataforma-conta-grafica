# Guia de Testes - Plataforma Conta Gráfica

## 📋 Visão Geral

Esta suite de testes foi criada para garantir a qualidade e confiabilidade da Plataforma Conta Gráfica. Os testes cobrem os principais módulos do sistema:

- **database.py** - Gerenciamento de banco de dados SQLite
- **excel_handler.py** - Exportação de relatórios para Excel
- **modulo_concilia.py** - Funções utilitárias de conciliação de PDFs
- **Testes de Integração** - Fluxo completo entre módulos

## 🚀 Como Executar os Testes

### 1. Instalar Dependências

Primeiro, instale todas as dependências necessárias:

```bash
pip install -r requirements.txt
```

### 2. Executar Todos os Testes

```bash
pytest
```

### 3. Executar com Cobertura

Para ver a cobertura de código:

```bash
pytest --cov=. --cov-report=html
```

Isso criará um relatório HTML em `htmlcov/index.html` que você pode abrir no navegador.

### 4. Executar Testes Específicos

**Executar apenas testes de um módulo:**
```bash
pytest tests/test_database.py
```

**Executar apenas testes de integração:**
```bash
pytest tests/test_integracao.py
```

**Executar um teste específico:**
```bash
pytest tests/test_database.py::TestDatabasePMPV::test_criar_sessao
```

### 5. Executar com Mais Detalhes

```bash
pytest -v -s
```
- `-v`: modo verboso (mostra cada teste)
- `-s`: mostra prints durante os testes

## 📁 Estrutura dos Testes

```
plataforma-conta-grafica/
├── tests/
│   ├── __init__.py
│   ├── test_database.py          # Testes do banco de dados
│   ├── test_excel_handler.py     # Testes de exportação Excel
│   ├── test_modulo_concilia.py   # Testes de conciliação
│   └── test_integracao.py        # Testes de integração
├── pytest.ini                     # Configuração do pytest
├── requirements.txt               # Dependências
└── README_TESTES.md              # Este arquivo
```

## 🧪 Cobertura de Testes

### test_database.py
✅ Criação de banco de dados  
✅ Criação de tabelas  
✅ Criar sessão  
✅ Salvar dados mensais  
✅ Substituir dados existentes  
✅ Carregar dados mensais  
✅ Salvar resultados  
✅ Tratamento de campos faltantes  

### test_excel_handler.py
✅ Criar arquivo Excel  
✅ Gerar nome com timestamp  
✅ Criar abas corretas  
✅ Cabeçalhos corretos  
✅ Cálculos de valores  
✅ Aba de resumo com totais  
✅ Filtrar dados vazios  
✅ Formatação numérica  

### test_modulo_concilia.py
✅ Conversão de valores monetários BR  
✅ Formatação brasileira  
✅ Limpeza de texto OCR  
✅ Extração de valores de PDFs  
✅ Filtros de anos e valores pequenos  
✅ Imutabilidade de PdfItem  

### test_integracao.py
✅ Fluxo completo: salvar BD → exportar Excel  
✅ Recuperar dados e reexportar  
✅ Cálculos PMPV simples e complexos  
✅ Cálculo de preço final  
✅ Cálculo trimestral completo  

## 🎯 Fixtures Utilizadas

### `db_temp`
Cria um banco de dados temporário para testes isolados. É automaticamente limpo após cada teste.

### `dados_exemplo`
Fornece dados de exemplo padronizados para testes.

### `resultado_exemplo`
Fornece resultados de exemplo para validação.

### `tmp_path`
Fixture do pytest que cria um diretório temporário único para cada teste.

## 🔍 Exemplos de Uso

### Testar uma Função Específica

```python
# Arquivo: test_custom.py
import pytest
from modulo_concilia import br_money_to_float

def test_minha_conversao():
    valor = br_money_to_float("R$ 1.234,56")
    assert valor == 1234.56
```

Execute:
```bash
pytest test_custom.py
```

### Usar Mock para Testes

```python
def test_com_mock(mocker):
    # Mock de uma função
    mock_func = mocker.patch('modulo.funcao')
    mock_func.return_value = "valor_mockado"
    
    # Seu teste aqui
    resultado = modulo.funcao()
    assert resultado == "valor_mockado"
```

## 📊 Relatórios de Cobertura

Após executar com `--cov`, você verá algo assim:

```
---------- coverage: platform win32, python 3.x -----------
Name                        Stmts   Miss  Cover
-----------------------------------------------
database.py                    45      2    96%
excel_handler.py               68      4    94%
modulo_concilia.py            102     12    88%
-----------------------------------------------
TOTAL                         215     18    92%
```

## 🐛 Debugging de Testes

### Ver Output Detalhado
```bash
pytest -vv -s
```

### Parar no Primeiro Erro
```bash
pytest -x
```

### Ver Traceback Completo
```bash
pytest --tb=long
```

### Rodar Apenas Testes que Falharam
```bash
pytest --lf
```

## 💡 Boas Práticas

1. **Sempre rode os testes antes de fazer commit**
2. **Crie testes para novos recursos**
3. **Mantenha os testes isolados** (use fixtures)
4. **Nomeie os testes de forma descritiva**
5. **Um teste deve testar apenas uma coisa**
6. **Use mocks para dependências externas**

## 🆘 Problemas Comuns

### Erro: "Module not found"
Solução: Certifique-se de estar no diretório correto e ter instalado as dependências:
```bash
cd plataforma-conta-grafica
pip install -r requirements.txt
```

### Erro: "fixture 'tmp_path' not found"
Solução: Atualize o pytest:
```bash
pip install --upgrade pytest
```

### Testes muito lentos
Solução: Execute testes específicos ou use pytest-xdist para paralelização:
```bash
pip install pytest-xdist
pytest -n auto  # Roda em paralelo
```

## 📚 Recursos Adicionais

- [Documentação do pytest](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [pytest-mock](https://pytest-mock.readthedocs.io/)

## 🤝 Contribuindo

Ao adicionar novos testes:

1. Siga a convenção de nomenclatura: `test_<funcionalidade>.py`
2. Use docstrings descritivas
3. Agrupe testes relacionados em classes
4. Adicione markers quando apropriado (`@pytest.mark.slow`)
5. Atualize este README se necessário

---

**Versão:** 1.0  
**Última Atualização:** 2026-02-12
