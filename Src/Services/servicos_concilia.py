"""Conciliação (RP): leitura do valor das notas de débito em PDF."""

import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass
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


def _faixa_normal(valor: float) -> bool:
    """Descarta só extremos inválidos: aceita de 0,01 (exclusive) a 999.999.999.
    Valores como 2024–2027 que aparecem em R$ são válidos e não são filtrados."""
    return 0.01 < valor < 999_999_999


def _valores_na_faixa(trechos: list[str], na_faixa) -> list[float]:
    """Converte cada trecho "1.234,56" em número e fica só com os que `na_faixa` aceita."""
    return [v for v in map(parse_brl, trechos) if na_faixa(v)]


def _nome_tem(arq: Path, trecho: str) -> bool:
    """O nome do arquivo, sem acento e em minúsculas, contém `trecho`?"""
    return trecho in _sem_acento(arq.name).lower()


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
    def extrair_valor(text: str) -> tuple[float, str]:
        """Valor principal do PDF: o maior valor achado pela primeira estratégia que
        encontra algo (1: "Total"/"Débito"; 2: R$; 3: número no fim da linha;
        4: qualquer número no formato BR)."""
        
        if not text:
            return 0.0, "Texto vazio"
        
        text_clean = RegrasConcilia.clean_ocr_text(text)

        lista_floats = []

        # Estratégia 1: padrões de "Total" ou "Débito" — os mais confiáveis,
        # porque indicam explicitamente o valor total.
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
            lista_floats += _valores_na_faixa(re.findall(pattern, text_clean, re.IGNORECASE), _faixa_normal)

        # Estratégia 2: sem padrão de "Total", qualquer valor precedido de R$.
        if not lista_floats:
            lista_floats = _valores_na_faixa(re.findall(r'R\$\s*([\d.]+,\d{2})', text_clean), _faixa_normal)

        # Estratégia 3: PDFs sem "Total" nem "R$" — valor no fim da linha.
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
            lista_floats = _valores_na_faixa(re.findall(pattern_isolado, text_clean, re.MULTILINE), _faixa_normal)

        # Estratégia 4 (último recurso): qualquer número no formato BR no texto.
        # Se nenhuma das estratégias acima encontrou nada (ex: valor não ocupa a
        # linha inteira sozinho), varre o texto todo por números no padrão
        # brasileiro sem exigir "R$" nem linha isolada. Faixa mais estreita
        # (1,00 a 999.999,99) porque aqui não há rótulo confirmando o valor.
        if not lista_floats:
            pattern_numero_br = r'\b(\d{1,3}(?:\.\d{3})*,\d{2})\b'
            lista_floats = _valores_na_faixa(re.findall(pattern_numero_br, text_clean), lambda v: 1.00 <= v <= 999_999.99)

        if lista_floats:
            return max(lista_floats), "Maior Valor Válido Detectado"
        return 0.0, "Valor não identificado"

    @staticmethod
    def processar_arquivos(arquivos: list[Path], categoria: str, log_callback,
                           raiz: Path | None = None) -> list[PdfItem]:
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
            if _nome_tem(arq, "cancelado"):
                canceladas.append(arq)
                continue
            nd = _numero_nd(arq.name)
            if not nd:
                por_nd.setdefault(f"__sem_nd__{arq}", arq)
                continue
            existente = por_nd.get(nd)
            if existente is None or (_nome_tem(arq, "atualiz") and not _nome_tem(existente, "atualiz")):
                por_nd[nd] = arq
        arquivos = list(por_nd.values()) + canceladas

        itens = []
        total = len(arquivos)

        for i, arq in enumerate(arquivos):
            log_callback(f"[{i+1}/{total}] Lendo: {arq.name}...")
            
            try:
                texto, metodo_leitura = read_pdf_text(arq)
                
                if texto:
                    valor, metodo_extracao = RegrasConcilia.extrair_valor(texto)
                    status = "OK" if valor > 0 else "REVISAR"
                    metodo_final = f"{metodo_leitura} -> {metodo_extracao}"

                    # Notas de débito canceladas (substituídas por uma "ATUALIZADO")
                    # entram com valor negativo, pois já foram cobradas/lançadas e
                    # precisam ser estornadas do total do período.
                    if _nome_tem(arq, "cancelado"):
                        valor = -valor
                else:
                    valor = 0.0
                    status = "ERRO"
                    metodo_final = "Sem texto extraído"

            except Exception as e:
                valor = 0.0
                status = "ERRO"
                metodo_final = f"Exceção: {str(e)[:50]}"

            itens.append(PdfItem(
                file_name=arq.name,
                file_path=str(arq),
                category="Receita" if eh_top(rel(arq)) else categoria,
                amount=valor,
                status=status,
                method=metodo_final
            ))
        
        return itens