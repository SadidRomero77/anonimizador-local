"""Núcleo del anonimizador. Solo biblioteca estándar de Python.

Detecta datos sensibles frecuentes en documentos en español de Colombia y los
cambia por marcadores consistentes: [PERSONA_1], [CEDULA_1], etc.
No es infalible: siempre se revisa el resultado a mano antes de usarlo.
"""
import re
import json

TIPOS = {
    "CORREO": "Correos electrónicos",
    "NIT": "NIT",
    "CEDULA": "Cédulas",
    "TELEFONO": "Teléfonos",
    "RADICADO": "Radicados y números de proceso",
    "DIRECCION": "Direcciones",
    "CUENTA": "Cuentas bancarias y tarjetas",
    "VALOR": "Valores en pesos",
    "PERSONA": "Nombres de personas",
    "FIRMA": "Firmas (imagen, trazo o firma digital en PDF)",
}

# Palabras que anuncian que sigue el nombre de una persona.
TITULOS = (
    "señor", "señora", "señores", "sr", "sra", "doctor", "doctora", "dr", "dra",
    "afiliado", "afiliada", "abogado", "abogada", "apoderado", "apoderada",
    "arrendatario", "arrendadora", "arrendador", "arrendataria", "demandante",
    "demandado", "demandada", "don", "doña", "ciudadano", "ciudadana",
    "solicitante", "peticionario", "peticionaria", "cliente", "usuario", "usuaria",
    "atentamente", "cordialmente", "nombre", "responsable", "asistentes",
    # Firmas y bloques de responsables (comunes en documentos colombianos)
    "firma", "firmado por", "firmante", "elaboró", "elaborado por", "proyectó", "revisó",
    "revisado por", "aprobó", "aprobado por", "representante legal", "funcionario", "funcionaria",
    "trabajador", "trabajadora", "empleado", "empleada", "contratista", "titular", "beneficiario",
    "beneficiaria", "accionante", "tutelante", "deudor", "deudora", "codeudor", "codeudora",
    "propietario", "propietaria", "testigo", "paciente", "a nombre de",
    # Inglés (formularios como el W-8BEN, facturas)
    "name", "full name", "print name", "signed by", "signature", "mr", "mrs", "ms", "dear",
)

# Etiquetas que, en la línea anterior, anuncian que la siguiente línea es un nombre (formularios).
_ETIQUETAS_NOMBRE = re.compile(
    r"(?i)\b(nombres?|apellidos?|name|beneficiari[oa]|beneficial owner|titular|contratista|contratante|"
    r"cliente|firma|signature|signed|señor(es|a)?|debe a|páguese a|pagar a|a favor de|a nombre de|"
    r"representante|propietari[oa]|arrendatari[oa]|deudor[a]?|trabajador[a]?|empleado|afiliado)\b")

# Palabras de títulos y encabezados: una línea que las contiene no es un nombre de persona.
_ENCABEZADO = {
    "cuenta", "cobro", "certificado", "certificación", "certificacion", "certificate", "constancia",
    "factura", "invoice", "recibo", "contrato", "acta", "informe", "formulario", "form", "república",
    "republica", "ministerio", "departamento", "secretaría", "gobierno", "nacional", "municipio",
    "alcaldía", "alcaldia", "universidad", "empresa", "total", "valor", "página", "pagina", "page",
    "status", "united", "states", "department", "treasury", "internal", "revenue", "service",
    "instructions", "part", "tax", "foreign", "owner", "withholding", "reporting", "individuals",
    "señores", "asunto", "referencia", "resolución", "resolucion", "decreto", "ley", "artículo",
    "articulo", "capítulo", "capitulo", "anexo", "tabla", "servicios", "honorarios", "concepto",
}


# Palabras con mayúscula que pueden ir pegadas a un nombre pero no son parte de él.
# Al encontrar una, el nombre se corta ahí («Marta Gómez Gerente» -> «Marta Gómez»).
_NO_NOMBRE = {
    "gerente", "abogado", "abogada", "representante", "director", "directora", "coordinador",
    "coordinadora", "jefe", "asesor", "asesora", "contador", "contadora", "revisor", "presidente",
    "secretario", "secretaria", "profesional", "auxiliar", "analista", "apoderado", "apoderada",
    "cédula", "cedula", "cc", "c.c", "nit", "tel", "teléfono", "telefono", "celular", "cel", "correo",
    "email", "dirección", "direccion", "calle", "carrera", "bogotá", "bogota", "medellín", "medellin",
    "cali", "barranquilla", "cartagena", "bucaramanga", "colombia", "sas", "ltda", "s.a.s", "firma",
    "atentamente", "cordialmente", "señor", "señora", "doctor", "doctora", "dr", "dra", "que", "el",
    "en", "con", "por", "para", "quien", "identificado", "identificada", "mayor", "vecino", "vecina",
    "domiciliado", "domiciliada", "solicita", "presenta", "manifiesta", "declara", "fecha", "asunto",
    "referencia", "ref", "radicado", "proceso", "juzgado", "tribunal", "notaría", "notaria", "banco",
    "eps", "ips", "cargo", "área", "area", "oficina", "general",
    # inglés: «NAME OF INDIVIDUAL» no es un nombre
    "of", "the", "and", "for", "to", "in", "on", "who", "is", "by", "date", "country", "address",
}

_MAY = "A-ZÁÉÍÓÚÑÜ"
_CAP = rf"[{_MAY}][a-záéíóúñü]+(?:-[{_MAY}][a-záéíóúñü]+)?"   # Gómez, Pérez-Gómez
_CAPS = rf"[{_MAY}]{{2,}}(?:-[{_MAY}]{{2,}})?"                 # GÓMEZ (firmas en mayúscula)
_PALABRA = rf"(?:{_CAP}|{_CAPS})"
_CONECTOR = r"(?:(?i:de)[ \t]+(?i:la|las|los)|(?i:de|del|la|las|los|y))"  # «de la Hoz», «del Castillo»
_NOMBRE = rf"{_PALABRA}(?:[ \t]+(?:{_CONECTOR}[ \t]+)?{_PALABRA}){{1,5}}"
_CONECTORES = ("de", "del", "la", "las", "los", "y")

# ---------- Direcciones (nomenclatura colombiana) ----------
# Las direcciones no cruzan líneas: se usa [ \t] y no \s para no tragarse la línea siguiente.
_E = r"[ \t]"
_VIA = (rf"(?i:Avenida{_E}+(?:Calle|Carrera)|Av\.?{_E}*(?:Calle|Carrera|Cra\.?|Cl\.?|Kr\.?)|Autopista|Carrera|Calle"
        r"|Cra\.?|Kra\.?|Cr\.?|Cll\.?|Cl\.?|Diagonal|Diag\.?|Dg\.?|Transversal|Trans\.?|Tv\.?|Tr\.?|Avenida|Av\.?"
        r"|Kr\.?|AK|AC|Circular|Circ\.?|Cir\.?)")
_NOMBRE_LUGAR = rf"{_PALABRA}(?:{_E}+(?:{_CONECTOR}{_E}+)?{_PALABRA}){{0,3}}"
_VIA_NOMBRE = rf"(?i:Avenida|Av\.?){_E}+{_NOMBRE_LUGAR}"  # Avenida Boyacá
_NUM = rf"\d{{1,3}}{_E}?[A-Za-z]?(?![A-Za-z])(?:{_E}?(?i:bis))?(?:{_E}?[A-Za-z](?![A-Za-z]))?"
_CARDINAL = rf"(?:{_E}+(?i:sur|norte|este|oeste))?"
_SEP = r"(?:#|N[o°º]\.?|Nro\.?|N[úu]mero)"
_COMPL = (rf"(?:{_E}*,?{_E}*(?:(?i:interior|int|apartamento|apto|apt|torre|casa|bloque|oficina|of|local|piso|etapa"
          rf"|manzana|mz|lote)\b\.?{_E}*(?:N[o°º]\.?{_E}*)?[\w-]{{1,6}}"
          rf"|(?i:barrio|br|urbanizaci[oó]n|urb|conjunto|conj|edificio|ed)\b\.?{_E}+{_NOMBRE_LUGAR}))*")
_DIRECCION = (rf"\b(?:{_VIA}{_E}*{_NUM}{_CARDINAL}{_E}*{_SEP}?|{_VIA_NOMBRE}{_E}*{_SEP})"
              rf"{_E}*{_NUM}{_E}*[-–]{_E}*\d{{1,3}}{_CARDINAL}{_COMPL}")
_RURAL = (rf"\b(?i:manzana|mz)\.?{_E}*\w{{1,4}}{_E}*,?{_E}*(?i:casa|cs|lote|lt)\.?{_E}*\d{{1,4}}{_COMPL}"
          rf"|\b(?i:km|kil[oó]metro){_E}*\d+(?:[.,]\d+)?{_E}+(?i:v[ií]a){_E}+(?:(?i:a|al){_E}+)?{_NOMBRE_LUGAR}"
          rf"|\b(?i:vereda|finca|hacienda|parcela){_E}+{_NOMBRE_LUGAR}")
# Etiqueta «Dirección: ...» para formas que no siguen la nomenclatura.
# (?<![\[\w]) evita tocar los marcadores ya puestos, como [DIRECCION_1].
_DIRECCION_ETIQUETA = (r"(?<![\[\w])(?i:direcci[oó]n(?:\s+de\s+(?:residencia|notificaci[oó]n(?:es)?|correspondencia"
                       r"|domicilio|entrega))?|domicilio|reside\s+en|residente\s+en)[ \t]*:?[ \t]*"
                       r"(?P<dato>(?![\s\[])[^\n;,\[]{3,80}?)(?=[ \t]*(?:[,;\n]|\.\s|\.?$))")


def _parece_direccion(dato):
    return bool(re.search(r"\d|(?i:vereda|finca|barrio|conjunto|edificio|manzana|sector|km)", dato))


# ---------- Cuentas bancarias y tarjetas ----------
_BANCOS = (r"(?:Bancolombia|Davivienda|BBVA|Scotiabank(?:\s+Colpatria)?|Colpatria|AV\s?Villas|Ita[úu]"
           r"|GNB(?:\s+Sudameris)?|Sudameris|Bancoomeva|Coopcentral|Bancam[ií]a|Nequi|Daviplata|Movii"
           r"|Lulo(?:\s+Bank)?|Nu\s?bank|Rappipay|Banco\s+(?:de\s+Bogot[áa]|Popular|de\s+Occidente|Caja\s+Social"
           r"|Agrario|Falabella|Pichincha|Serfinanza|W|Mundo\s+Mujer|Finandina|Santander|Cooperativo\s+Coopcentral))")
_PALABRA_CTA = (r"(?:de|del|en|el|la|banco|bancaria|bancario|ahorros?|corriente|n[oó]mina|n[úu]mero|nro\.?"
                rf"|no\.?|n°|nº|#|{_BANCOS})")
_CUENTA_ETIQUETA = (rf"(?i)\b(?:cuenta|cta\.?|ahorros?|corriente|{_BANCOS})(?:[\s,]+{_PALABRA_CTA}\b\.?)*"
                    r"\s*[:#]?\s*(?P<dato>\d+(?:[ .-]\d+){0,5})(?!\d)")
_IBAN = r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b"
_TARJETA = r"(?<![\d-])(?:\d{4}[ -]){3}\d{4}(?:[ -]?\d{1,3})?(?![\d-])|(?<!\d)\d{15,16}(?!\d)"


def _digitos(s):
    return re.sub(r"\D", "", s)


def _cuenta_valida(dato):
    d = _digitos(dato)
    return 6 <= len(d) <= 24 and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dato.strip())  # no fechas


def _luhn(dato):
    d = _digitos(dato)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, c in enumerate(reversed(d)):
        n = int(c)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


# El orden importa: lo más específico primero. Cada entrada es (tipo, regex) o (tipo, regex, filtro).
# Si el regex tiene el grupo «dato», solo se cambia ese grupo y se conserva la etiqueta («C.C.», «cuenta»).
PATRONES = [
    ("CORREO", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("NIT", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-\d\b")),
    ("DIRECCION", re.compile(_DIRECCION)),
    ("DIRECCION", re.compile(_RURAL)),
    ("CUENTA", re.compile(_IBAN), lambda d: len(_digitos(d)) >= 10),
    ("CUENTA", re.compile(_TARJETA), _luhn),
    ("CUENTA", re.compile(_CUENTA_ETIQUETA), _cuenta_valida),
    ("CUENTA", re.compile(r"(?<![\d-])\d{3}-\d{6}-\d{2}(?![\d-])")),  # formato Bancolombia 000-000000-00
    ("TELEFONO", re.compile(r"(?<!\d)(?:\+?57[\s.-]?)?(?:3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}|60\d[\s.-]?\d{3}[\s.-]?\d{4})(?!\d)")),
    ("CEDULA", re.compile(
        r"(?i)(?:\bC\.?\s?C\.?|\bc[eé]dula(?:\s+de\s+ciudadan[ií]a)?|\bidentificad[oa]\s+con(?:\s+la)?(?:\s+C\.?\s?C\.?)?)"
        r"\s*(?:No\.?|n[úu]mero|N°|#)?\s*:?\s*(?P<dato>\d[\d.\s]{4,13}\d)")),
    ("CEDULA", re.compile(r"(?<![\d.$])\b\d{1,3}(?:\.\d{3}){2}\b(?!\.\d)(?!\s*(?:pesos|COP|mil|millones))(?!\d)")),
    ("RADICADO", re.compile(r"\b[A-Z]{2,6}-\d{4}-\d{3,6}\b|\b\d{5}-\d{2}-\d{2}-\d{3}-\d{4}-\d{5}-\d{2}\b")),
    ("RADICADO", re.compile(r"(?:(?<=número )|(?<=Número )|(?<=radicado )|(?<=radicada )|(?<=No\. )|(?<=N° ))\d[\d-]{2,}\d")),
    ("DIRECCION", re.compile(_DIRECCION_ETIQUETA), _parece_direccion),
    ("VALOR", re.compile(r"\$\s?\d(?:[\d.,]*\d)?(?:\s?(?:COP|millones|mil))?")),
]


def _tokens_validos(nombre):
    return len([t for t in nombre.split() if t.lower() not in _CONECTORES]) >= 2


def _recortar(nombre):
    """Corta el nombre en la primera palabra que no es de persona («Marta Gómez Gerente» -> «Marta Gómez»)."""
    tokens = []
    for t in nombre.split():
        if t.lower().strip(".,:;") in _NO_NOMBRE:
            break
        tokens.append(t)
    while tokens and tokens[-1].lower() in _CONECTORES:  # no terminar en «de la»
        tokens.pop()
    return " ".join(tokens)


def _formas(texto):
    """Regex con el texto tal cual, en MAYÚSCULAS y en Tipo Título: el nombre se encuentra como esté escrito."""
    titulo = " ".join(t if t.lower() in _CONECTORES else t[:1].upper() + t[1:].lower() for t in texto.split())
    return "|".join(re.escape(f) for f in dict.fromkeys((texto, texto.upper(), titulo)))


def _extender(nombre, texto):
    """Formas más largas del mismo nombre: si se halló «Marta Gómez» pero también aparece
    «Marta Gómez Rivas», devuelve esta última para que no quede expuesto el segundo apellido."""
    patron = rf"(?<!\w)(?:{_formas(nombre)})(?:[ \t]+(?:{_CONECTOR}[ \t]+)?{_PALABRA}){{1,2}}(?!\w)"
    largos = []
    for m in re.finditer(patron, texto):
        largo = _recortar(m.group(0))
        if len(largo.split()) > len(nombre.split()):
            largos.append(largo)
    return largos


def encontrar_nombres(texto, extra=()):
    """Nombres propuestos: los que tú indicas más los que siguen a un título."""
    hallados = []
    for n in extra:
        n = n.strip()
        if n:
            hallados.append(n)
    titulos = "|".join(TITULOS)
    patron = re.compile(rf"(?i:\b(?:{titulos})\b)\.?\s*:?\s*,?\s*({_NOMBRE})")
    for m in patron.finditer(texto):
        n = _recortar(m.group(1).strip())
        if _tokens_validos(n):
            hallados.append(n)
    # Firma: el nombre en las líneas que siguen a «Atentamente», «Firma» o a una raya de firma (_____).
    lineas = texto.splitlines()
    for i, linea in enumerate(lineas[:-1]):
        if re.fullmatch(r"(?i)\s*(atentamente|cordialmente|respetuosamente|firma(do)?|[_.\-]{5,})\s*[,:]?\s*", linea):
            for sig in lineas[i + 1:i + 7]:
                s = _recortar(sig.strip().strip(","))
                if s and re.fullmatch(_NOMBRE, s) and _tokens_validos(s):
                    hallados.append(s)
                    break
    # Formularios: una línea que es solo un nombre, sin título delante («JUAN PÉREZ» en un campo).
    # Para no confundirla con un encabezado se exige una de dos pruebas:
    #   - el mismo nombre aparece 2 o más veces en el documento (encabezado y firma), o
    #   - la línea anterior termina con una etiqueta: «Nombre», «Name», «Beneficiario», «Firma»...
    for i, linea in enumerate(lineas):
        s = linea.strip().strip(",.;:")
        cand = _recortar(s)
        if not cand or not s.startswith(cand) or len(cand.split()) > 6:
            continue
        if not re.fullmatch(_NOMBRE, cand) or not _tokens_validos(cand):
            continue
        if any(t.lower().strip(".,") in _ENCABEZADO for t in cand.split()):
            continue
        anterior = next((x for x in reversed(lineas[:i]) if x.strip()), "")
        repetido = len(re.findall(rf"(?<!\w)(?:{_formas(cand)})(?!\w)", texto)) >= 2
        if repetido or _ETIQUETAS_NOMBRE.search(anterior[-60:]):
            hallados.append(cand)
    # Formas más largas del mismo nombre (segundo apellido, segundo nombre).
    for n in list(hallados):
        hallados.extend(_extender(n, texto))
    vistos, salida = set(), []
    for n in hallados:
        k = n.lower()
        if k not in vistos:
            vistos.add(k)
            salida.append(n)
    return salida


def _variantes(nombre):
    """El nombre completo y cada par contiguo de palabras (nombre y apellido)."""
    pal = nombre.split()
    v = {nombre}
    for i in range(len(pal) - 1):
        for j in range(i + 2, len(pal) + 1):
            # Nunca «de la» ni «María de»: cambiaría esas palabras en todo el documento.
            if pal[i].lower() not in _CONECTORES and pal[j - 1].lower() not in _CONECTORES:
                v.add(" ".join(pal[i:j]))
    for p in pal:
        if len(p) >= 5:
            v.add(p)
    return sorted(v, key=len, reverse=True)


def anonimizar(texto, tipos=None, nombres_extra=(), excluir=(), registro=None):
    """Devuelve (texto_anonimo, mapa, informe).

    mapa: marcador -> valor original (para restaurar, guárdalo solo en tu equipo).
    informe: tipo -> cantidad de datos distintos cambiados.
    excluir: valores que no se deben cambiar (falsos positivos conocidos).
    registro: lista opcional; recibe cada (texto_original_exacto, marcador) cambiado.
              Se usa para tachar esos mismos textos dentro de un PDF.
    """
    if registro is None:
        registro = []
    tipos = set(tipos) if tipos is not None else set(TIPOS)
    excluir = {e.strip().lower() for e in excluir if e.strip()}
    mapa, inverso, contadores = {}, {}, {}

    def marcador(tipo, valor):
        clave = (tipo, re.sub(r"\s+", " ", valor.strip().lower()))
        if clave in inverso:
            return inverso[clave]
        contadores[tipo] = contadores.get(tipo, 0) + 1
        m = f"[{tipo}_{contadores[tipo]}]"
        inverso[clave] = m
        mapa[m] = valor.strip()
        return m

    # 1) Nombres primero: así sus partes no se confunden con otros patrones.
    if "PERSONA" in tipos:
        cubiertos = set()
        for nombre in sorted(encontrar_nombres(texto, nombres_extra), key=len, reverse=True):
            if nombre.lower() in excluir or nombre.lower() in cubiertos:
                continue
            cubiertos.update(v.lower() for v in _variantes(nombre))
            m = marcador("PERSONA", nombre)
            for var in _variantes(nombre):
                rx = re.compile(rf"(?<!\w)(?:{_formas(var)})(?!\w)")
                # Se guarda el texto tal como aparece («MARTA GÓMEZ»): en el PDF hay que buscarlo así.
                for escrito in dict.fromkeys(x.group(0) for x in rx.finditer(texto)):
                    registro.append((escrito, m))
                texto = rx.sub(m, texto)

    # 2) Patrones de formato.
    for tipo, rx, *resto in PATRONES:
        if tipo not in tipos:
            continue
        filtro = resto[0] if resto else None

        def cambiar(match, tipo=tipo, filtro=filtro):
            completo = match.group(0)
            if completo.strip().lower() in excluir:
                return completo
            grupo = "dato" if "dato" in match.re.groupindex else 0
            dato = match.group(grupo)
            if dato.strip().lower() in excluir or (filtro and not filtro(dato)):
                return completo
            m = marcador(tipo, dato)
            registro.append((dato.strip(), m))
            if grupo:  # el dato está en el grupo; se conserva la etiqueta ("C.C.", "cuenta")
                return completo[: match.start(grupo) - match.start(0)] + m \
                    + completo[match.end(grupo) - match.start(0):]
            return m

        texto = rx.sub(cambiar, texto)

    informe = {t: contadores[t] for t in TIPOS if t in contadores}
    return texto, mapa, informe


def restaurar(texto, mapa):
    """Vuelve a poner los datos originales usando el mapa guardado."""
    for m in sorted(mapa, key=len, reverse=True):
        texto = texto.replace(m, mapa[m])
    return texto


def leer_docx(ruta_o_bytes):
    """Extrae el texto de un .docx sin dependencias externas."""
    import io
    import zipfile
    import xml.etree.ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    origen = io.BytesIO(ruta_o_bytes) if isinstance(ruta_o_bytes, (bytes, bytearray)) else ruta_o_bytes
    with zipfile.ZipFile(origen) as z:
        raiz = ET.fromstring(z.read("word/document.xml"))
    parrafos = []
    for p in raiz.iter(f"{ns}p"):
        parrafos.append("".join(t.text or "" for t in p.iter(f"{ns}t")))
    return "\n".join(parrafos)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python anonimizador.py archivo.txt|archivo.docx")
        raise SystemExit(1)
    ruta = sys.argv[1]
    contenido = leer_docx(ruta) if ruta.lower().endswith(".docx") else open(ruta, encoding="utf-8").read()
    salida, mapa, informe = anonimizar(contenido)
    print(salida)
    print("\n--- Informe ---")
    print(json.dumps(informe, ensure_ascii=False, indent=2))
