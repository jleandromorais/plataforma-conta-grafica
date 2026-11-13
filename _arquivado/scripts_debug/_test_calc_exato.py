"""Testa _extrair_calc_exato com textos reais dos PDFs."""
import re

def _extrair_calc_exato(texto: str) -> float:
    m = re.search(
        r'((?:\d{1,3}(?:[.\s]\d{3})*|\d{4,})(?:,\d+)?)'
        r'\s*(?:m[³3]|mmbtu)?\s*[xX×]\s*'
        r'R\$\s*((?:\d{4,}|\d{1,3}(?:[.\s]\d{3})*)(?:[,.]\d+)?)',
        texto,
    )
    if not m:
        return 0.0
    try:
        vol  = float(m.group(1).replace(' ','').replace('.','').replace(',','.'))
        taxa = float(m.group(2).replace(' ','').replace('.','').replace(',','.'))
        if vol > 0 and taxa > 0:
            return vol * taxa
    except ValueError:
        pass
    return 0.0

casos = [
    # (texto, valor_pdf_arredondado, descricao)
    ("Periodo 1 a 30 de Novembro/2025 = 49.779,00 m³ X R$2,8532 = R$142.029,44",
     142029.44, "AMBEV NDPFP"),
    ("Periodo 1 a 30 de Novembro/2025 = 9.964,00 m³ X R$2,8349 = R$ 28.246,94",
     28246.94, "CBA NDPFP"),
    ("Periodo 1 a 30 de Novembro/2025 = 36.674,00 X R$2,8532 = R$104.638,26",
     104638.26, "AMBEV TOPNREC"),
    ("Periodo 1 a 30 de Setembro/2025 = 50400,1988 m³ X R$ 2,7736 = R$139789,99",
     139789.99, "INDORAMA TOPNREC"),
    ("Periodo 1 a 30 de Novembro/2025 = 185,00 m³ X R$2,8480 = R$ 526,88",
     526.88, "INDORAMA FIBRAS NDPFP"),
    ("Periodo 1 a 30 de Novembro/2025 = 3.959,00 m³ X R$2,8500 = R$ 11.283,15",
     11283.15, "NISSIN NDPFP"),
    # sem padrão (OAC Congest/SOP) → deve retornar 0.0
    ("Motivo: NOTA DEBITO SOP Quantidade: 4103.24\nValor Unitário: R$ 4,54\nValor Total Débito: R$ 18.610,40",
     0.0, "OAC SOP (sem padrão vol×taxa)"),
]

print(f"{'Descricao':<30} {'PDF(2dec)':>14} {'Exato(6dec)':>18} {'Diferenca':>12}")
print('-' * 78)
total_melhoria = 0.0
for texto, arredondado, desc in casos:
    exato = _extrair_calc_exato(texto)
    if arredondado == 0.0:
        print(f"  {desc:<28} {'(sem padrão)':>14} {exato:>18.6f}")
    else:
        diff = exato - arredondado
        total_melhoria += diff
        print(f"  {desc:<28} {arredondado:>14,.2f} {exato:>18.6f} {diff:>+12.6f}")

print('-' * 78)
print(f"  Ganho total de precisão nos NDPFPs+TOP (somado): {total_melhoria:+.6f}")
print()
print("  Nota: o ganho é pequeno (~0,003 por arquivo) mas elimina os erros")
print("  de arredondamento acumulados ao longo do cálculo.")
