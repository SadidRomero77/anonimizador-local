"""Genera empaquetado/icono.ico: un documento con datos tachados."""
from pathlib import Path
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, S - 8, S - 8), radius=48, fill=(31, 99, 181))       # fondo azul
d.rounded_rectangle((62, 36, 194, 220), radius=14, fill=(255, 255, 255))        # hoja
for i, (ancho, tachado) in enumerate([(100, False), (70, True), (100, False), (55, True), (85, False)]):
    y = 66 + i * 30
    color = (11, 31, 58) if tachado else (170, 185, 205)
    d.rounded_rectangle((80, y, 80 + ancho, y + (18 if tachado else 10)), radius=4, fill=color)
img.save(Path(__file__).with_name("icono.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icono.ico listo")
