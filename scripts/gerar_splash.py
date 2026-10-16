"""Gera Src/assets/splash.png — tela de abertura exibida pelo .exe (PyInstaller
Splash) enquanto o Python e as bibliotecas carregam.

Uso: python scripts/gerar_splash.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
ASSETS = RAIZ / "Src" / "assets"
W, H = 480, 260
FUNDO = (32, 33, 36)
TEXTO = (240, 240, 240)
MUTED = (150, 154, 160)
ACENTO = (41, 128, 185)   # azul do Módulo 1 (PMPV)


def _fonte(nome: str, tamanho: int):
    try:
        return ImageFont.truetype(str(Path("C:/Windows/Fonts") / nome), tamanho)
    except OSError:
        return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 4], fill=ACENTO)

    icone = Image.open(ASSETS / "icons8-cash-94.png").convert("RGBA").resize((72, 72), Image.LANCZOS)
    img.paste(icone, (40, 70), icone)

    d.text((128, 76), "GraphAccount Pro", font=_fonte("segoeuib.ttf", 30), fill=TEXTO)
    d.text((130, 118), "Gestão de Conta Gráfica", font=_fonte("segoeui.ttf", 16), fill=MUTED)
    # O texto "Abrindo…" é desenhado pelo PyInstaller (text_pos no .spec).

    img.save(ASSETS / "splash.png")
    print("ok:", ASSETS / "splash.png")


if __name__ == "__main__":
    main()
