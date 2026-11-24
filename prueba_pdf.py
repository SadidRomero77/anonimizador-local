"""Prueba del PDF: crea un PDF de ejemplo, lo anonimiza y verifica que los datos reales ya no estén."""
import pymupdf

from pdf_anon import anonimizar_pdf, leer_pdf

TEXTO = """Bogotá, 12 de octubre de 2026
Señora Marta Lucía Gómez Rivas, identificada con C.C. 52.123.456.
Dirección: Calle 45 # 12-34 apto 301, barrio Chapinero. Teléfono 310 555 0147.
Correo: marta.gomez@correo.com. Vive también en Manzana C casa 14.
Consignar en la cuenta de ahorros Bancolombia No. 123-456789-01.
Tarjeta 4111 1111 1111 1111. Cuenta corriente Davivienda 0570 0012 3456.
Atentamente,
Julián Andrés Torres Mejía"""

REALES = ["Marta", "Gómez Rivas", "52.123.456", "Calle 45", "12-34", "310 555 0147", "marta.gomez",
          "Manzana C", "123-456789-01", "4111 1111", "0570 0012 3456", "Julián", "Torres Mejía"]

doc = pymupdf.open()
pag = doc.new_page()
pag.insert_text((50, 72), TEXTO, fontsize=10)
doc.set_metadata({"author": "Marta Gómez", "title": "Documento de Marta"})
original = doc.tobytes()

pdf, texto, mapa, informe, no_ubicados = anonimizar_pdf(original)
print(texto)
print(informe, "no ubicados:", no_ubicados)

salida = leer_pdf(pdf)
for r in REALES:
    assert r not in salida, f"quedó en el PDF: {r}"
    assert r not in texto, f"quedó en el texto: {r}"
assert "[PERSONA_" in salida and "[CUENTA_" in salida and "[DIRECCION_" in salida
meta = pymupdf.open(stream=pdf, filetype="pdf").metadata
assert not meta.get("author") and not meta.get("title"), meta
assert not no_ubicados

# Párrafo con fuente incrustada (como un PDF exportado desde Word): el texto se parte en varias
# líneas. Los datos deben desaparecer y las palabras vecinas (arriba, abajo y al lado) quedarse.
doc = pymupdf.open()
pag = doc.new_page(width=420, height=200)
pag.insert_htmlbox(pymupdf.Rect(20, 20, 400, 190), "<p style='font-family:sans-serif;font-size:10pt'>"
                   "Señora Marta Lucía Gómez Rivas, C.C. 52.123.456, vive en Calle 45 # 12-34 apto 301, barrio "
                   "Chapinero. Teléfono 310 555 0147. Consignar en la cuenta de ahorros Bancolombia No. "
                   "123-456789-01. Tarjeta 4111 1111 1111 1111. Gracias por su atención.</p>")
pdf, texto, mapa, informe, no_ubicados = anonimizar_pdf(doc.tobytes())
salida = " ".join(leer_pdf(pdf).split())
for r in ["Marta", "Gómez", "52.123.456", "Calle 45", "Chapinero", "310 555", "123-456789-01", "4111"]:
    assert r not in salida, f"quedó en el PDF: {r}"
for v in ["Señora", "C.C.", "vive en", "Teléfono", "Consignar en la cuenta de ahorros Bancolombia No.",
          "Tarjeta", "Gracias por su atención"]:
    assert v in salida, f"se borró texto que no era sensible: {v!r}\n{salida}"

# Firmas: imagen de firma escaneada y firma vectorial (tableta) se borran; el logo del membrete se queda.
doc = pymupdf.open()
pag = doc.new_page()  # carta 612 x 792
def imagen(rect, color):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 30), 0)
    pix.set_rect(pix.irect, color)
    pag.insert_image(rect, pixmap=pix)
imagen(pymupdf.Rect(50, 30, 170, 90), (31, 99, 181))           # logo arriba
pag.insert_text((50, 130), "Señora Marta Gómez presentó la solicitud.", fontsize=11)
pag.insert_text((50, 150), "Luego Marta Gómez Rivas pidió revisión.", fontsize=11)
pag.insert_text((50, 200), "Atentamente,", fontsize=11)
imagen(pymupdf.Rect(50, 210, 230, 265), (20, 20, 90))           # firma escaneada
pag.insert_text((50, 285), "MARTA GÓMEZ RIVAS", fontsize=11)
pag.insert_text((50, 360), "Revisó:", fontsize=11)
trazo = pag.new_shape()
for i in range(12):                                              # firma vectorial
    x = 60 + i * 12
    trazo.draw_bezier((x, 390), (x + 4, 370), (x + 8, 410), (x + 12, 390))
trazo.finish(color=(0, 0, 0), width=1.5)
trazo.commit()
pag.insert_text((50, 430), "Pedro Nel Rojas Vélez", fontsize=11)
pag.insert_text((50, 445), "Abogado", fontsize=11)

pdf, texto, mapa, informe, no_ubicados = anonimizar_pdf(doc.tobytes())
salida = pymupdf.open(stream=pdf, filetype="pdf")[0]
txt = " ".join(salida.get_text().split())
assert informe.get("FIRMA") == 2, informe
assert len(salida.get_image_info()) == 1, "el logo debe quedarse y la firma escaneada irse"
assert not [d for d in salida.get_drawings() if any(it[0] == "c" for it in d["items"])], "quedó la firma vectorial"
for r in ["Marta", "Gómez", "Rivas", "MARTA", "GÓMEZ", "RIVAS", "Pedro", "Vélez"]:
    assert r not in txt, f"quedó en el PDF: {r}"
for v in ["Atentamente", "Revisó", "Abogado", "presentó la solicitud"]:
    assert v in txt, f"se borró texto que no era sensible: {v}"

# Etiqueta a la izquierda en la misma fila («Firma/Sello: [imagen]»), etiqueta en inglés y firma
# puesta como anotación de tinta (Adobe «Rellenar y firmar»).
def oscuridad(pagina, zona):
    pix = pagina.get_pixmap(clip=zona, dpi=72, colorspace=pymupdf.csGRAY)
    return sum(1 for b in pix.samples if b < 200) / len(pix.samples)

doc = pymupdf.open()
pag = doc.new_page()
def poner(rect, color):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 30), 0)
    pix.set_rect(pix.irect, color)
    pag.insert_image(rect, pixmap=pix)
pag.insert_text((50, 140), "Certificamos que el documento es auténtico.", fontsize=11)
pag.insert_text((240, 620), "Firma/Sello:", fontsize=11)
z1 = pymupdf.Rect(330, 594, 560, 646)
poner(z1, (10, 10, 120))                                   # firma a la derecha de la etiqueta
pag.insert_text((50, 700), "Signature:", fontsize=11)
z2 = pymupdf.Rect(50, 705, 200, 745)
poner(z2, (10, 10, 120))                                   # firma bajo «Signature»
z3 = pymupdf.Rect(400, 690, 540, 740)
tinta = pag.add_ink_annot([[(405, 720), (430, 695), (455, 735), (480, 700), (535, 725)]])
tinta.set_border(width=3)
tinta.update()
z4 = pymupdf.Rect(60, 300, 200, 360)
poner(z4, (200, 30, 30))                                   # foto o gráfico sin palabra clave cerca
original = doc.tobytes()

pdf, texto, mapa, informe, no_ubicados = anonimizar_pdf(original)
p = pymupdf.open(stream=pdf, filetype="pdf")[0]
assert informe.get("FIRMA") == 3, informe
for z in (z1, z2):
    assert oscuridad(p, z + (2, 2, -2, -2)) < 0.05, f"quedó la firma en {z}"
assert not list(p.annots()), "quedó la anotación de firma"
assert oscuridad(p, z4) > 0.5, "se borró una imagen que no era firma"

pdf, texto, mapa, informe, no_ubicados = anonimizar_pdf(original, todas_las_imagenes=True)
p = pymupdf.open(stream=pdf, filetype="pdf")[0]
assert oscuridad(p, z4 + (2, 2, -2, -2)) < 0.05, "con «todas las imágenes» debía borrarse"
assert "IMAGEN" in informe, informe

# Formulario lleno: el valor escrito en el campo (nombre, cédula) se aplana a texto y se anonimiza.
doc = pymupdf.open()
pag = doc.new_page()
pag.insert_text((50, 80), "CUENTA DE COBRO", fontsize=14)
pag.insert_text((50, 120), "Nombre del contratista:", fontsize=11)
for y, valor in ((130, "LAURA MARCELA QUINTERO SOTO"), (180, "C.C. 1.020.304.050")):
    campo = pymupdf.Widget()
    campo.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    campo.field_name = f"campo{y}"
    campo.rect = pymupdf.Rect(50, y, 400, y + 20)
    campo.field_value = valor
    pag.add_widget(campo)
pag.insert_text((50, 260), "Atentamente,", fontsize=11)
pag.insert_text((50, 300), "Laura Marcela Quintero Soto", fontsize=11)
pdf, texto, mapa, informe, no_ubicados = anonimizar_pdf(doc.tobytes())
salida = pymupdf.open(stream=pdf, filetype="pdf")
txt = " ".join(salida[0].get_text().split())
for r in ["Quintero", "QUINTERO", "1.020.304.050"]:
    assert r not in txt, f"quedó en el formulario: {r}"
assert "CUENTA DE COBRO" in txt and "Nombre del contratista" in txt
assert not list(salida[0].widgets()), "no deben quedar campos de formulario"
print("OK PDF")
