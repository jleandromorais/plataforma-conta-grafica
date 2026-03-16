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
        regras = RegrasConcilia
        text_clean = regras.clean_ocr_text(text)
        text_upper = text_clean.upper()
        
        # Identifica se é um documento oficial para ser mais rigoroso no filtro
        eh_documento_oficial = any(x in text_upper for x in ["NOTA", "PENALIDADE", "FISCAL"])
        todos_valores = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})", text_clean)
        
        lista_floats = []
        if todos_valores:
            for v in todos_valores:
                f = parse_brl(v)
                # Filtro de anos para evitar falsos positivos
                if f in [2024.0, 2025.0, 2026.0, 2027.0]: continue
                
                if eh_documento_oficial:
                    if f > 0: lista_floats.append(f)
                else:
                    if f > 50: lista_floats.append(f) # Filtro de ruído para outros docs

        if lista_floats:
            return max(lista_floats), "Maior Valor Detectado"

        return 0.0, "Valor não identificado"

    @staticmethod
    def processar_arquivos(arquivos: List[Path], categoria: str, log_callback) -> List[PdfItem]:
        itens = []
        total = len(arquivos)
        
        for i, arq in enumerate(arquivos):
            log_callback(f"[{i+1}/{total}] Lendo: {arq.name}...")
            
            texto, metodo_leitura = read_pdf_text(arq)
            if texto:
                valor, metodo_extracao = RegrasConcilia.extrair_valor(texto)
                status = "OK" if valor > 0 else "REVISAR"
                metodo_final = f"{metodo_leitura} -> {metodo_extracao}"
            else:
                valor = 0.0
                status = "ERRO"
                metodo_final = metodo_leitura
                
            itens.append(PdfItem(arq.name, str(arq), categoria, valor, status, metodo_final))
            
        return itens