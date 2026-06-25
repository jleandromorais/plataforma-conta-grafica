"""
Design System central do GraphAccount Pro.

Este módulo é a *fonte única da verdade* para cores, tipografia e
espaçamento da interface. Todas as telas devem importar daqui em vez de
escrever cores/fontes "soltas" no meio do código.

Por quê: antes, cada tela inventava suas próprias cores e tamanhos
(títulos de 24 a 32px, headers ora ciano ora transparentes, botões verdes
numa tela e azuis em outra). Centralizar aqui garante que o produto pareça
*um só sistema coeso* — e que uma mudança de marca seja feita num lugar só.
"""

import customtkinter as ctk

# ──────────────────────────────────────────────────────────────────────────
# 1. COR DE MARCA E TEMA GLOBAL
# ──────────────────────────────────────────────────────────────────────────
# Paleta oficial: "slate" (base Tailwind). Uma única cor de marca, usada como
# acento em todo o app.
COR_MARCA = "#3b82f6"   # azul (Tailwind blue-500)

# Estado do tema (claro/escuro). Pode ser alternado em runtime pelo botão ☀️/🌙.
_APPEARANCE_ATUAL = "Dark"


def configure_theme(appearance_mode: str = "Dark", color_theme: str = "blue") -> None:
    """
    Aplica a configuração global de tema do CustomTkinter.

    Deve ser chamada uma vez no ponto de entrada da aplicação
    antes de criar qualquer janela CTk / CTkToplevel.
    """
    global _APPEARANCE_ATUAL
    _APPEARANCE_ATUAL = appearance_mode
    ctk.set_appearance_mode(appearance_mode)
    ctk.set_default_color_theme(color_theme)


def alternar_tema() -> str:
    """Alterna entre tema claro e escuro em runtime. Retorna o novo modo."""
    global _APPEARANCE_ATUAL
    _APPEARANCE_ATUAL = "Light" if _APPEARANCE_ATUAL == "Dark" else "Dark"
    ctk.set_appearance_mode(_APPEARANCE_ATUAL)
    return _APPEARANCE_ATUAL


def tema_atual() -> str:
    """Retorna o modo de aparência atual ('Dark' ou 'Light')."""
    return _APPEARANCE_ATUAL


# ──────────────────────────────────────────────────────────────────────────
# 2. CORES SEMÂNTICAS  (paleta "slate")
# ──────────────────────────────────────────────────────────────────────────
# Cor em UI deve SIGNIFICAR algo. Use estas constantes pelo significado da
# ação, não pela cor em si. Assim, navegação fica neutra e a cor destaca
# apenas o que importa (ação principal, perigo, etc.).
COR_PRIMARIA       = "#3b82f6"   # ação principal: Calcular, Processar, Confirmar
COR_PRIMARIA_HOVER = "#2563eb"
COR_SUCESSO        = "#10b981"   # salvar, exportar com sucesso
COR_SUCESSO_HOVER  = "#059669"
COR_PERIGO         = "#ef4444"   # apagar, remover, cancelar
COR_PERIGO_HOVER   = "#dc2626"
COR_AVISO          = "#f59e0b"   # importar, atenção
COR_AVISO_HOVER    = "#d97706"
COR_NEUTRA         = "#334155"   # botões de navegação (sem significado de ação)
COR_NEUTRA_HOVER   = "#475569"
COR_ROXO           = "#8b5cf6"   # acento secundário (salvar/registrar)
COR_ROXO_HOVER     = "#7c3aed"

# Superfícies / fundos
COR_FUNDO        = "#0f172a"   # fundo geral da tela (slate-900)
COR_HEADER       = "#1e293b"   # faixa de cabeçalho das telas (slate-800)
COR_CARD         = "#1e293b"   # blocos de detalhe/cards (slate-800)
COR_CARD_ALT     = "#263548"   # linha alternada (zebra) sobre card
COR_INPUT        = "#334155"   # campos de entrada / superfícies elevadas
COR_REALCE       = "#1e1b4b"   # realce de linha/bloco importante (indigo)
COR_DESTAQUE     = "#f59e0b"   # número de resultado final (o que o olho busca)

# Texto
COR_TEXTO           = "#f8fafc"   # texto principal sobre fundo escuro
COR_TEXTO_TITULO    = "#f8fafc"
COR_TEXTO_SUBTITULO = "#94a3b8"
COR_TEXTO_SUAVE     = "#94a3b8"
COR_MUTED           = "#94a3b8"   # texto secundário / legendas


# ──────────────────────────────────────────────────────────────────────────
# 3. TIPOGRAFIA (uma escala, não números soltos)
# ──────────────────────────────────────────────────────────────────────────
_FAMILIA = "Roboto"

FONTE_TITULO    = (_FAMILIA, 24, "bold")   # título da tela (discreto, padronizado)
FONTE_SUBTITULO = (_FAMILIA, 14)           # descrição abaixo do título
FONTE_SECAO     = (_FAMILIA, 18, "bold")   # título de bloco/painel
FONTE_RESULTADO = (_FAMILIA, 28, "bold")   # número final em destaque
FONTE_CORPO     = (_FAMILIA, 13)           # texto comum
FONTE_LABEL     = (_FAMILIA, 12, "bold")   # rótulos de campo
FONTE_PEQUENA   = (_FAMILIA, 11)           # legendas, dicas


# ──────────────────────────────────────────────────────────────────────────
# 4. ESPAÇAMENTO (escala 4 / 8 / 16 / 24)
# ──────────────────────────────────────────────────────────────────────────
# Use SEMPRE um destes valores para padding/margem. Espaçamento consistente
# é o que faz a interface parecer "alinhada" em vez de "torta".
ESP_XS = 4
ESP_SM = 8
ESP_MD = 16
ESP_LG = 24
