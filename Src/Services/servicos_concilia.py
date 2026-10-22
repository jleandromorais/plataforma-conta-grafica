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
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
from Src.common.formatting import parse_brl
from Src.infrastructure.ocr.ocr_pdf import read_pdf_text


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def eh_top(caminho: str | Path) -> bool:
    """TOP não recuperável (pasta "TOP Não Recup", "NDTOPNREC...", "TOP.NREC...").
    "top" como palavra isolada, para não pegar "Desktop"."""
    return re.search(r"(?<![a-z])top(?![a-z])", _sem_acento(str(caminho)).lower()) is not None


def _substituido(arq: Path) -> bool:
    """Versões antigas guardadas em subpasta "Substituídos"/"substituídas"."""
    return any("substitu" in _sem_acento(p).lower() for p in arq.parent.parts)


def _numero_nd(nome: str) -> str | None:
    """Número da ND para deduplicar original × atualizada: "NDPFP03882",
    "ND - TOP NREC 03864", "NDTOPNREC03901", "TOP.NREC - 4430_4313"."""
    m = re.search(r"(PFP|TOPNREC)(\d+)", re.sub(r"[^A-Z0-9]", "", _sem_acento(nome).upper()))
    return m.group(0) if m else None


# Padrão RP: a planilha oficial "Conta Gráfica" lança receitas e despesas de
# penalidade líquidas de PIS/COFINS (9,25%) — ex.: "=15764.98*(1-0.0925)".
# Os itens guardam o valor bruto da nota; totais e RP usam o líquido.
FATOR_PIS_COFINS = 1 - 0.0925


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
                    except (ValueError, AttributeError):
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
                except (ValueError, AttributeError):
                    pass
        
        # ============================================================================
        # ESTRATÉGIA 3: PDFs sem "Total" nem "R$" — valor no fim da linha
        # ============================================================================
        # Algumas notas de débito (ex: Eneva/Petrolina/Garanhuns) trazem o valor
        # sem "R$" na frente — às vezes com separador de milhar ("25.790,68"), às
        # vezes sem ("143,15"). O valor fica no fim da linha, sozinho ou depois de
        # um texto: na ND Petrolina de jan-26 o total vem como
        # "30/01/2026 15.764,98" e as parcelas como "... DEZ-25 11.779,43".
        # Exigir a linha inteira pegava só a parcela isolada (3.985,55).
        # CEP/CNPJ/datas não terminam em vírgula com 2 casas, então ancorar o
        # número no fim da linha (MULTILINE) não gera falso positivo.
        if not lista_floats:
            pattern_isolado = r'(?:^|\s)(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
            matches = re.findall(pattern_isolado, text_clean, re.MULTILINE)

            for m in matches:
                try:
                    f = parse_brl(m)
                    if 0.01 < f < 999_999_999:
                        lista_floats.append(f)
                except (ValueError, AttributeError):
                    pass

        # ============================================================================
        # ESTRATÉGIA 4: Último recurso — qualquer número em formato BR no texto
        # ============================================================================
        # Se nenhuma das estratégias acima encontrou nada (ex: valor não ocupa a
        # linha inteira sozinho), varre o texto todo por números no padrão
        # brasileiro sem exigir "R$" nem linha isolada, e usa o maior valor válido.
        if not lista_floats:
            pattern_numero_br = r'\b(\d{1,3}(?:\.\d{3})*,\d{2})\b'
            matches = re.findall(pattern_numero_br, text_clean)

            for m in matches:
                try:
                    f = parse_brl(m)
                    if 1.00 <= f <= 999_999.99:
                        lista_floats.append(f)
                except (ValueError, AttributeError):
                    pass

        # ============================================================================
        # RETORNAR O RESULTADO
        # ============================================================================

        if lista_floats:
            valor_final = max(lista_floats)  # Retorna o maior valor encontrado
            return valor_final, "Maior Valor Válido Detectado"

        return 0.0, "Valor não identificado"

    @staticmethod
    def processar_arquivos(arquivos: List[Path], categoria: str, log_callback,
                           raiz: Path | None = None) -> List[PdfItem]:
        """
        Processa lista de arquivos PDF e extrai valores.
        
        Args:
            arquivos: Lista de caminhos dos PDFs
            categoria: "Receita" ou "Despesa"
            log_callback: Função para registrar log
            raiz: Pasta escolhida; TOP/Substituídos são detectados só no
                caminho dentro dela (o resto do caminho pode ter qualquer nome)
            
        Returns:
            Lista de PdfItem com os dados extraídos
        """
        # TOP não recuperável entra no RP como RECEITA (planilha oficial, linha
        # "TOP não recuperável" dentro de Receitas), mesmo quando a subpasta
        # TOP foi guardada na pasta de despesas (caso de fev-26).
        # Versões antigas em subpastas "Substituídos" ficam de fora.
        def rel(arq: Path) -> Path:
            return arq.relative_to(raiz) if raiz and arq.is_relative_to(raiz) else arq

        arquivos = [a for a in arquivos if not _substituido(rel(a))]

        # Deduplica por número de ND (ex: "NDPFP03882", "NDTOPNREC03901"):
        # quando duas notas do mesmo número existem (original + retificada),
        # mantém a que tem "atualiz"/"atualizado" no nome; se nenhuma tiver,
        # mantém a primeira.
        # Notas "cancelado" ficam de fora da dedupe: elas entram com valor
        # negativo (ver abaixo) e devem ser somadas junto com a atualizada,
        # não descartadas.
        por_nd: dict[str, Path] = {}
        canceladas = []
        for arq in arquivos:
            if "cancelado" in _sem_acento(arq.name).lower():
                canceladas.append(arq)
                continue
            nd = _numero_nd(arq.name)
            if not nd:
                por_nd.setdefault(f"__sem_nd__{arq}", arq)
                continue
            existente = por_nd.get(nd)
            if existente is None:
                por_nd[nd] = arq
            elif "atualiz" in _sem_acento(arq.name).lower() and "atualiz" not in _sem_acento(existente.name).lower():
                por_nd[nd] = arq
        arquivos = list(por_nd.values()) + canceladas

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

                    # Notas de débito canceladas (substituídas por uma "ATUALIZADO")
                    # entram com valor negativo, pois já foram cobradas/lançadas e
                    # precisam ser estornadas do total do período.
                    if "cancelado" in _sem_acento(arq.name).lower():
                        valor = -valor
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
                category="Receita" if eh_top(rel(arq)) else categoria,
                amount=valor,
                status=status,
                method=metodo_final
            )
            itens.append(item)
        
        return itens