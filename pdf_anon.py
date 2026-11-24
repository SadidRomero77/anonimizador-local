"""Soporte de PDF: leer el texto y producir un PDF anonimizado.

Usa PyMuPDF. El PDF de salida no solo tapa los datos: la redacción BORRA el
texto original de la página y escribe encima el marcador ([PERSONA_1], ...).
También se eliminan metadatos (autor, título), adjuntos, enlaces, JavaScript
y valores de formularios.
"""
import pymupdf

from anonimizador import anonimizar


class PdfSinTexto(ValueError):
    """El PDF es una imagen escaneada: no hay texto que anonimizar."""


def _abrir(datos):
    doc = pymupdf.open(stream=datos, filetype="pdf")
    if doc.needs_pass:
        doc.close()
        raise ValueError("El PDF está protegido con contraseña. Quítale la contraseña y vuelve a intentarlo.")
    return doc


def _preparar(datos, quitar_firmas=False):
    """Abre el PDF y lo deja listo para anonimizar. Devuelve (doc, firmas_previas).

    1. Si se piden firmas, quita los campos de firma digital y las firmas puestas como anotación
       («Rellenar y firmar» de Adobe, Vista previa de Mac, sellos) y anota dónde estaban.
    2. «Aplana» el formulario: los valores escritos en sus campos pasan a ser texto normal de la
       página. Sin esto, el nombre o la cédula escritos en un formulario no se detectan.
    3. Reescribe el archivo: repara referencias internas rotas, frecuentes en formularios, que
       hacían fallar el proceso («cannot find object in xref»).
    firmas_previas: {número de página: [rectángulos]} de las firmas quitadas en el paso 1.
    """
    doc = _abrir(datos)
    previas = {}
    for n, pagina in enumerate(doc):
        if not quitar_firmas:
            break
        zonas = []
        try:
            for campo in [w for w in pagina.widgets() if w.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE]:
                zonas.append(pymupdf.Rect(campo.rect))
                pagina.delete_widget(campo)
            xrefs = [a.xref for a in pagina.annots(types=(pymupdf.PDF_ANNOT_INK, pymupdf.PDF_ANNOT_STAMP))]
            for xref in xrefs:
                anot = pagina.load_annot(xref)
                zonas.append(pymupdf.Rect(anot.rect))
                pagina.delete_annot(anot)
        except Exception:  # un campo dañado no debe detener todo; la limpieza final lo quita
            pass
        if zonas:
            previas[n] = zonas
    try:
        doc.bake(annots=True, widgets=True)
    except Exception:
        pass  # sin campos que aplanar o formulario dañado: se sigue con el texto que haya
    limpio = doc.tobytes(garbage=3)
    doc.close()
    return pymupdf.open(stream=limpio, filetype="pdf"), previas


def _limpiar(doc):
    """Quita metadatos (autor, título), adjuntos, enlaces, JavaScript y formularios.
    Si la limpieza completa falla en un PDF dañado, se hace lo esencial paso a paso."""
    try:
        doc.scrub(redactions=False)
    except Exception:
        for paso in (lambda: doc.del_xml_metadata(),
                     lambda: [doc.embfile_del(n) for n in doc.embfile_names()],
                     lambda: [p.delete_link(l) for p in doc for l in p.get_links()]):
            try:
                paso()
            except Exception:
                pass
    doc.set_metadata({})


def _texto(doc):
    # Un párrafo del PDF viene partido en líneas visuales; se une en una sola línea para que un
    # dato partido («Calle 45 # 12-34 apto / 301») se detecte completo. search_for lo encuentra
    # igual en la página aunque cruce el salto de línea.
    parrafos = []
    for pagina in doc:
        for bloque in pagina.get_text("blocks", sort=True):
            if bloque[6] == 0:  # 0 = bloque de texto (1 = imagen)
                parrafo = " ".join(bloque[4].split())
                if parrafo:
                    parrafos.append(parrafo)
    texto = "\n".join(parrafos)
    if len(texto.strip()) < 20:
        raise PdfSinTexto("Este PDF no tiene texto seleccionable (parece escaneado o una foto). "
                          "Pásalo primero por un programa de OCR y vuelve a abrirlo.")
    return texto


def leer_pdf(datos):
    doc, _ = _preparar(datos)
    try:
        return _texto(doc)
    finally:
        doc.close()


# Textos que suelen estar junto a una firma. Sirven de «ancla»: solo se borran imágenes y trazos
# que estén cerca de uno de ellos (o del nombre de una persona), para no tocar logos ni gráficos.
# Anclas fuertes: palabras que casi siempre acompañan una firma (español e inglés).
# La búsqueda no distingue mayúsculas y encuentra la palabra dentro de otras
# («firma» encuentra «Firmado», «FIRMANTE»; «signature» encuentra «Signatures»).
_ANCLAS_FIRMA = (
    "firma", "rúbrica", "rubrica", "sello", "huella", "atentamente", "cordialmente", "respetuosamente",
    "suscrit", "_____", "revisó", "aprobó", "elaboró", "proyectó", "autorizó", "vo.bo", "vo. bo", "v.b.",
    "signature", "signed", "sign here", "sincerely", "regards",
)


def _cerca(r, anclas, margen_v, margen_h=60):
    zona = pymupdf.Rect(r.x0 - margen_h, r.y0 - margen_v, r.x1 + margen_h, r.y1 + margen_v)
    return any(zona.intersects(a) for a in anclas)


def _es_firma(r, pagina, fuertes, debiles):
    """¿Es una firma? Debe estar junto a una palabra clave:
    - arriba o abajo (hasta 90 pt), o en la misma fila a la izquierda o derecha (hasta 250 pt),
      como «Firma y sello: [imagen]»;
    - o casi encima del nombre de una persona o de «C.C.» (25 pt).
    En el membrete (parte alta de la página) se exige la palabra clave muy cerca: así no se borran logos."""
    if r.y1 < pagina.rect.height * 0.15:
        return _cerca(r, fuertes, 30)
    return _cerca(r, fuertes, 90) or _cerca(r, fuertes, 10, 250) or _cerca(r, debiles, 25, 20)


def _tamano_firma(r, pagina):
    """Una firma es mediana: ni un ícono diminuto ni media página (logos grandes, páginas escaneadas)."""
    p = pagina.rect
    return 15 <= r.width <= p.width * 0.6 and 8 <= r.height <= p.height * 0.3


def _zonas_de_firma(pagina, golpes, todas_las_imagenes=False, previas=()):
    """Rectángulos con firmas: las ya quitadas al preparar el PDF (campo de firma digital,
    anotación), más imágenes y trazos vectoriales (tableta) junto a una palabra clave."""
    debiles = [r for r, m in golpes if m.startswith("[PERSONA_")] + pagina.search_for("c.c.")
    fuertes = []
    for palabra in _ANCLAS_FIRMA:
        fuertes += pagina.search_for(palabra)
    zonas = list(previas)
    # Imágenes: firma escaneada o sello junto a una palabra clave (o todas, si el usuario lo pidió).
    for info in pagina.get_image_info():
        r = pymupdf.Rect(info["bbox"]) & pagina.rect
        if r.is_empty or r.width < 4 or r.height < 4:
            continue
        if todas_las_imagenes or (_tamano_firma(r, pagina) and _es_firma(r, pagina, fuertes, debiles)):
            zonas.append(r)
    # Cada zona es (rectángulo_para_borrar, rectángulo_visible); en imágenes y anotaciones son iguales.
    zonas = [(z, z) for z in zonas]
    if not fuertes and not debiles:
        return zonas
    # 4) Trazos con curvas (firma hecha con lápiz digital) junto a una palabra clave; se agrupan los vecinos.
    grupos = []  # [visible, para_borrar]
    for d in pagina.get_drawings():
        curvas = sum(1 for item in d["items"] if item[0] == "c")
        if curvas < 3:
            continue
        grosor = (d.get("width") or 1)
        visible = pymupdf.Rect(d["rect"]) + (-grosor, -grosor, grosor, grosor)
        if visible.width > pagina.rect.width * 0.6 or visible.height > pagina.rect.height * 0.3 \
                or not _es_firma(visible, pagina, fuertes, debiles):
            continue
        # MuPDF solo borra un trazo si la zona cubre también los puntos de control de las curvas y las
        # esquinas del trazo (pueden sobresalir varias veces su grosor). Por eso la zona de borrado lleva
        # un margen amplio. Solo se borra lo que cabe ENTERO en ella: las líneas largas (bordes de
        # tablas) no se tocan. El recuadro que se dibuja usa el tamaño visible, sin ese margen.
        borrar = pymupdf.Rect(d["rect"])
        for item in d["items"]:
            for punto in item[1:]:
                if isinstance(punto, pymupdf.Point):
                    borrar |= punto
        margen = max(25, 12 * grosor)
        borrar = borrar + (-margen, -margen, margen, margen)
        for g in grupos:
            if (g[0] + (-15, -15, 15, 15)).intersects(visible):
                g[0] |= visible
                g[1] |= borrar
                break
        else:
            grupos.append([visible, borrar])
    zonas += [(b, v) for v, b in grupos if v.width >= 15 and v.height >= 8]
    return zonas


def _borrar_firmas(pagina, golpes, contador, todas_las_imagenes=False, previas=()):
    """Borra las firmas de la página y deja un recuadro con [FIRMA_n]. Devuelve cuántas borró."""
    zonas = []
    for b, v in sorted(_zonas_de_firma(pagina, golpes, todas_las_imagenes, previas), key=lambda z: -z[1].width * z[1].height):
        if not any(ov.contains(v) for _, ov in zonas):  # la misma imagen puesta dos veces cuenta una
            zonas.append((b, v))
    if not zonas:
        return 0
    zonas.sort(key=lambda z: (round(z[1].y0), z[1].x0))  # numeradas de arriba abajo
    etiqueta = "IMAGEN" if todas_las_imagenes else "FIRMA"
    for b, _ in zonas:
        pagina.add_redact_annot(b, fill=False)
    # Solo imágenes y trazos: el texto cercano (nombre, cargo) se conserva o ya fue anonimizado.
    pagina.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                            graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                            text=pymupdf.PDF_REDACT_TEXT_NONE)
    for i, z in enumerate((v for _, v in zonas), start=contador + 1):
        pagina.draw_rect(z, color=(0.45, 0.45, 0.45), width=0.8, dashes="[3] 0", overlay=True)
        pagina.insert_text((z.x0 + 2, z.y0 + min(9, z.height - 1)), f"[{etiqueta}_{i}]",
                           fontname="helv", fontsize=min(8, max(4, z.height * 0.6)), color=(0.3, 0.3, 0.3))
    return len(zonas)


def _dibujar_marcadores(pagina, golpes):
    """Caja gris con el marcador encima de cada dato borrado (sin repetir cajas anidadas)."""
    dibujados = []
    for r, marcador in sorted(golpes, key=lambda g: g[0].width * g[0].height, reverse=True):
        if any(d.contains(r) for d in dibujados):  # «Gómez» dentro de «Marta Gómez»: ya está tapado
            continue
        dibujados.append(r)
        alto = r.height
        caja = pymupdf.Rect(r.x0, r.y0 + alto * 0.12, r.x1, r.y1 - alto * 0.12)
        pagina.draw_rect(caja, color=None, fill=(0.85, 0.85, 0.85), overlay=True)
        tam = min(9, alto * 0.6)
        while tam > 4 and pymupdf.get_text_length(marcador, "helv", tam) > r.width - 1:
            tam -= 0.5
        pagina.insert_text((r.x0 + 0.5, caja.y1 - (caja.height - tam * 0.72) / 2), marcador,
                           fontname="helv", fontsize=tam, color=(0, 0, 0), overlay=True)


def anonimizar_pdf(datos, tipos=None, nombres_extra=(), excluir=(), todas_las_imagenes=False):
    """Devuelve (pdf_bytes, texto_anonimo, mapa, informe, no_ubicados).

    no_ubicados: lista de (marcador, original) detectados en el texto que no se pudieron localizar en la
    página (por ejemplo, partidos en dos líneas). Hay que revisarlos a mano.
    todas_las_imagenes: borra todas las imágenes, no solo las firmas detectadas (respaldo manual).
    """
    quitar_firmas = todas_las_imagenes or tipos is None or "FIRMA" in tipos
    doc, previas = _preparar(datos, quitar_firmas)
    try:
        texto = _texto(doc)
        registro = []
        texto_anon, mapa, informe = anonimizar(texto, tipos, nombres_extra, excluir, registro)

        # Un mismo dato puede aparecer varias veces: se busca cada texto una sola vez.
        unicos = {}
        for original, marcador in registro:
            unicos.setdefault(original, marcador)
        encontrados = set()
        firmas = 0
        for n, pagina in enumerate(doc):
            golpes = []  # (rectángulo, marcador)
            # Lo más largo primero: «Marta Lucía Gómez» antes que «Gómez».
            for original in sorted(unicos, key=len, reverse=True):
                for quad in pagina.search_for(original, quads=True):  # si el dato se parte en 2 líneas, da 2 quads
                    encontrados.add(original)
                    r = quad.rect
                    golpes.append((r, unicos[original]))
                    # PyMuPDF borra todo carácter que toque el rectángulo. El rectángulo de búsqueda
                    # mide la línea completa y toca las líneas de arriba y abajo; por eso se borra
                    # solo con una franja central de la línea.
                    franja = pymupdf.Rect(r.x0 + 0.3, r.y0 + r.height * 0.3, r.x1 - 0.3, r.y1 - r.height * 0.3)
                    pagina.add_redact_annot(franja, fill=False)
            # Borra el texto de verdad; en imágenes solo se tapan los píxeles bajo el dato.
            pagina.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)  # respeta líneas de tablas
            _dibujar_marcadores(pagina, golpes)
            if todas_las_imagenes or tipos is None or "FIRMA" in tipos:
                firmas += _borrar_firmas(pagina, golpes, firmas, todas_las_imagenes, previas.get(n, ()))
        if firmas:
            informe["IMAGEN" if todas_las_imagenes else "FIRMA"] = firmas

        _limpiar(doc)
        pdf = doc.tobytes(garbage=4, deflate=True, clean=True)
        no_ubicados = sorted({(unicos[o], o) for o in unicos if o not in encontrados})
        return pdf, texto_anon, mapa, informe, no_ubicados
    finally:
        doc.close()
