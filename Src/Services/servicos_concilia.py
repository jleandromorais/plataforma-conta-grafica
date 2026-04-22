"""
CLASSE RegrasConcilia CORRIGIDA
Para: Src/Services/servicos_concilia.py

MUDANÇAS PRINCIPAIS:
1. Removido filtro perigoso que eliminava valores válidos (anos 2024-2027)
2. Adicionada detecção específica de padrões "Total"
3. Melhorado filtro de valores para apenas remover extremos inválidos
4. Mantém compatibilidade total com o código existente

Para usar: Copie e cole esta classe no seu arquivo servicos_concilia.py
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
from Src.common.formatting import parse_brl
from Src.infrastructure.ocr.ocr_pdf import read_pdf_text


@dataclass(frozen=True)
class PdfItem:
    file_name: str
    file_path: str
    category: str
    amount: float
    status: str
    method: str


class RegrasConcilia:
    """Regras de extração e processamento de valores de PDFs."""

    @staticmethod
    def clean_ocr_text(text: str) -> str:
        """Remove caracteres problemáticos do OCR."""
        if not text:
            return ""
        return (
            text.replace("|", "")
            .replace("!", "1")
            .replace("l", "1")
            .replace("$=", " ")
            .replace("=", " = ")
        )

    @staticmethod
    def extrair_valor(text: str) -> Tuple[float, str]:
        """
        Extrai o valor principal do documento PDF.
        
        ESTRATÉGIA:
        1. Primeiro tenta encontrar linhas com "Total" ou "Débito" explícito
        2. Se encontrar, usa esse valor
        3. Se não encontrar, procura por todos os valores em R$
        4. Retorna o maior valor encontrado
        
        IMPORTANTE: Removido o filtro que eliminava valores válidos como 2024, 2025, 2026, 2027
        """
        
        if not text:
            return 0.0, "Texto vazio"
        
        regras = RegrasConcilia
        text_clean = regras.clean_ocr_text(text)
        text_upper = text_clean.upper()
        
        lista_floats = []
        
        # ============================================================================
        # ESTRATÉGIA 1: Procurar por padrões específicos de "Total" ou "Débito"
        # ============================================================================
        # Esses padrões são mais confiáveis porque indicam explicitamente o valor total
        
        patterns_total = [
            # Padrão: "Total Nota de Débito ... = R$ XXXX,XX"
            r'Total\s+(?:Nota de Débito|Débito)[^=]*=\s*R?\$?\s*([\d.]+,\d{2})',
            
            # Padrão: "Total ... = R$ XXXX,XX" (genérico)
            r'(?:Total|TOTAL)[^=]*=\s*R?\$?\s*([\d.]+,\d{2})',
            
            # Padrão: "Valor Total Débito: R$ XXXX,XX"
            r'Valor Total Débito:\s*R?\$?\s*([\d.]+,\d{2})',
            
            # Padrão: "Total Débito: R$ XXXX,XX"
            r'(?:Total|TOTAL)\s+(?:Débito|Débito):\s*R?\$?\s*([\d.]+,\d{2})',
            
            # Padrão: "Valor Total: R$ XXXX,XX"
            r'Valor Total:\s*R?\$?\s*([\d.]+,\d{2})',
            
            # Padrão: "Valor a Pagar: R$ XXXX,XX"
            r'(?:Valor a Pagar|Valor a pagar):\s*R?\$?\s*([\d.]+,\d{2})',
        ]
        
        for pattern in patterns_total:
            matches = re.findall(pattern, text_clean, re.IGNORECASE)
            if matches:
                for m in matches:
                    try:
                        f = parse_brl(m)
                        # ✅ Filtro CORRETO: Remove apenas valores inválidos
                        # Aceita: 0.01 até 999.999.999
                        if 0.01 < f < 999_999_999:
                            lista_floats.append(f)
                    except:
                        pass
        
        # ============================================================================
        # ESTRATÉGIA 2: Se não encontrou com "Total", procura por todos os R$
        # ============================================================================
        # Fallback: Se não encontrou padrão específico, procura qualquer valor em R$
        
        if not lista_floats:
            pattern_rs = r'R\$\s*([\d.]+,\d{2})'
            matches = re.findall(pattern_rs, text_clean)
            
            for m in matches:
                try:
                    f = parse_brl(m)
                    # ✅ Mesmo filtro: Remove apenas valores inválidos
                    if 0.01 < f < 999_999_999:
                        lista_floats.append(f)
                except:
                    pass
        
        # ============================================================================
        # RETORNAR O RESULTADO
        # ============================================================================
        
        if lista_floats:
            valor_final = max(lista_floats)  # Retorna o maior valor encontrado
            return valor_final, "Maior Valor Válido Detectado"
        
        return 0.0, "Valor não identificado"

    @staticmethod
    def processar_arquivos(arquivos: List[Path], categoria: str, log_callback) -> List[PdfItem]:
        """
        Processa lista de arquivos PDF e extrai valores.
        
        Args:
            arquivos: Lista de caminhos dos PDFs
            categoria: "Receita" ou "Despesa"
            log_callback: Função para registrar log
            
        Returns:
            Lista de PdfItem com os dados extraídos
        """
        itens = []
        total = len(arquivos)
        
        for i, arq in enumerate(arquivos):
            # Log de progresso
            log_callback(f"[{i+1}/{total}] Lendo: {arq.name}...")
            
            try:
                # Extrai texto do PDF
                texto, metodo_leitura = read_pdf_text(arq)
                
                if texto:
                    # Extrai valor do texto
                    valor, metodo_extracao = RegrasConcilia.extrair_valor(texto)
                    status = "OK" if valor > 0 else "REVISAR"
                    metodo_final = f"{metodo_leitura} -> {metodo_extracao}"
                else:
                    valor = 0.0
                    status = "ERRO"
                    metodo_final = "Sem texto extraído"
                    
            except Exception as e:
                valor = 0.0
                status = "ERRO"
                metodo_final = f"Exceção: {str(e)[:50]}"
            
            # Cria item com dados extraídos
            item = PdfItem(
                file_name=arq.name,
                file_path=str(arq),
                category=categoria,
                amount=valor,
                status=status,
                method=metodo_final
            )
            itens.append(item)
        
        return itens