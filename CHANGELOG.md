# Changelog - Plataforma Conta Gráfica

## [1.1.0] - 2026-02-12

### ✅ Adicionado
- **Suite completa de testes** com pytest
  - 39 testes cobrindo todos os módulos principais
  - Testes unitários para `database.py`, `excel_handler.py` e `modulo_concilia.py`
  - Testes de integração para fluxo completo
  - Cobertura de cálculos PMPV
  
- **Arquivos de teste criados:**
  - `tests/__init__.py`
  - `tests/test_database.py` (8 testes)
  - `tests/test_excel_handler.py` (8 testes)
  - `tests/test_modulo_concilia.py` (11 testes)
  - `tests/test_integracao.py` (12 testes)
  - `pytest.ini` (configuração)
  - `README_TESTES.md` (documentação completa)

### 🔧 Corrigido

#### Problema: Arquivos com mesmo nome não podem ser abertos
**Sintoma:** Erro ao tentar exportar múltiplos relatórios ou quando arquivo Excel já está aberto

**Correções implementadas:**

1. **excel_handler.py**
   - Adicionado sistema de numeração incremental automática (`_1`, `_2`, etc.)
   - Verifica se arquivo está em uso antes de salvar
   - Fecha o workbook corretamente após salvar (`wb.close()`)
   - Melhor tratamento de erro ao abrir arquivo automaticamente
   - Timestamp mais preciso incluindo data completa

2. **modulo_concilia.py**
   - Timestamp melhorado de `%H%M%S` para `%Y%m%d_%H%M%S`
   - Sistema de verificação de arquivo em uso
   - Numeração incremental automática se arquivo já existe
   - Fecha workbook após salvar (`wb.close()`)

3. **database.py**
   - Corrigida ordem de configuração `row_factory` para permitir conversão correta de linhas em dicionários

### 📦 Dependências
- Adicionado `requirements.txt` com todas as dependências
- Dependências de teste: pytest, pytest-cov, pytest-mock

### 📊 Resultado dos Testes
```
============================= 39 passed =================================
- 8 testes de banco de dados: ✅ 100% passando
- 8 testes de exportação Excel: ✅ 100% passando  
- 11 testes de conciliação: ✅ 100% passando
- 12 testes de integração: ✅ 100% passando
```

## Como os problemas foram resolvidos

### Antes
```python
# Exportava sempre com mesmo nome se no mesmo segundo
timestamp = datetime.now().strftime("%H%M%S")
nome = f"Relatorio_{timestamp}.xlsx"
wb.save(nome)
# Se arquivo já aberto no Excel = ERRO!
```

### Depois
```python
# Timestamp único com data completa
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
nome_arquivo = f"Relatorio_PMPV_{timestamp}.xlsx"

# Detecta arquivo em uso e adiciona número
contador = 1
while arquivo_em_uso(nome_arquivo):
    nome_arquivo = f"Relatorio_PMPV_{timestamp}_{contador}.xlsx"
    contador += 1

wb.save(nome_arquivo)
wb.close()  # Fecha corretamente!
```

## Benefícios

✅ **Nunca mais perde dados** - Sempre cria novo arquivo se o anterior estiver aberto  
✅ **Nomes únicos** - Timestamp completo + numeração evita colisões  
✅ **Melhor gerenciamento** - Arquivos são fechados corretamente  
✅ **Qualidade garantida** - 39 testes automatizados validam o código  
✅ **Fácil manutenção** - Testes detectam bugs antes de afetar produção  

## Como executar os testes

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar todos os testes
pytest

# Com cobertura
pytest --cov=. --cov-report=html

# Apenas testes específicos
pytest tests/test_database.py
```

## Documentação

Consulte `README_TESTES.md` para documentação completa sobre:
- Como executar testes
- Estrutura dos testes
- Exemplos de uso
- Troubleshooting
