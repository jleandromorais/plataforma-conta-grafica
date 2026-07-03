# Submódulos de geração de abas do Excel Consolidado.
# Cada módulo expõe uma função sheet_<nome>(wb, ...) idêntica ao @staticmethod original.
from .sheet_sr import sheet_sr
from .sheet_pr import sheet_pr
from .sheet_pv import sheet_pv
from .sheet_progresso import sheet_progresso
from .sheet_dashboard import sheet_dashboard

__all__ = [
    "sheet_sr",
    "sheet_pr",
    "sheet_pv",
    "sheet_progresso",
    "sheet_dashboard",
]
