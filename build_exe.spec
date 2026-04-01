# -*- mode: python ; coding: utf-8 -*-
# Spec file para gerar o .exe da Plataforma Financeira
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Coleta assets do customtkinter (temas, fontes, imagens internas)
ctk_datas = collect_data_files("customtkinter")

a = Analysis(
    ["main_dashboard.py"],
    pathex=["."],
    binaries=[],
    datas=[
        *ctk_datas,
    ],
    hiddenimports=[
        "customtkinter",
        "PIL._tkinter_finder",
        "openpyxl",
        "openpyxl.styles.builtins",
        "pandas",
        "pandas.io.formats.excel",
        "xlsxwriter",
        "lxml",
        "lxml.etree",
        "sqlite3",
        # módulos do projeto
        "database",
        "excel_handler",
        "modulo_pmpv",
        "modulo_cgf",
        "modulo_rpv",
        "modulo_scg",
        "modulo_ret",
        "modulo_concilia_RP",
        "modulo_auditoria_CGR",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PlataformaFinanceira",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # sem janela de terminal preta
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PlataformaFinanceira",
)
