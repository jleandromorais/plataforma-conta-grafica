import customtkinter as ctk


def configure_theme(appearance_mode: str = "Dark", color_theme: str = "blue") -> None:
    """
    Aplica a configuração global de tema do CustomTkinter.

    Deve ser chamada uma vez no ponto de entrada da aplicação
    antes de criar qualquer janela CTk / CTkToplevel.
    """
    ctk.set_appearance_mode(appearance_mode)
    ctk.set_default_color_theme(color_theme)

