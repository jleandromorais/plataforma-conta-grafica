r"""Runtime hook do PyInstaller: garante que DLLs nativas (numpy, matplotlib)
carreguem mesmo quando o .exe roda de um caminho de rede (UNC, ex: \\SERVIDOR\...).

O Windows restringe LoadLibrary de caminhos UNC por padrão (Safe DLL Search
Mode), o que causa falhas intermitentes ao importar extensões .pyd que
dependem de DLLs vizinhas. Registrar o diretório explicitamente via
os.add_dll_directory contorna essa restrição.
"""
import os
import sys

if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    _base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    try:
        os.add_dll_directory(_base)
    except (OSError, FileNotFoundError):
        pass
