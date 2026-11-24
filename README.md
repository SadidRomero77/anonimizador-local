# Anonimizador local

App para Windows que cambia datos sensibles de un documento por marcadores (`[PERSONA_1]`, `[CUENTA_1]`…).
Lee `.pdf`, `.docx` y `.txt`. **Todo ocurre en tu computador: ningún documento sale a internet.**

## Descarga

En [Releases](../../releases/latest) descarga:

- **`Anonimizador.exe`**: doble clic y se abre la app en el navegador. No necesita instalar Python.
- **`Anonimizador-USB.zip`**: la misma app más un instalador de acceso directo y las instrucciones, lista para copiar a una memoria USB.

Funciona en Windows 10 y 11 (64 bits). La primera vez Windows puede mostrar *"Windows protegió su PC"* porque el programa no está firmado: pulsa **Más información → Ejecutar de todas formas**.

## Qué detecta

- Nombres de personas, cédulas, NIT, teléfonos, correos y radicados.
- Direcciones (Calle, Carrera, Av., Diagonal, Transversal, apto, torre, barrio, manzana/casa, vereda…).
- Valores en pesos y cuentas bancarias (ahorros, corriente, Nequi/Daviplata, IBAN, tarjetas validadas con Luhn).
- Firmas en PDF: imagen escaneada, trazo de lápiz digital y campos de firma digital.

En PDF genera un archivo nuevo donde los datos se **borran** (no solo se tapan) y escribe el marcador encima. También quita metadatos, adjuntos, enlaces y JavaScript. Un PDF escaneado no tiene texto: primero hay que pasarlo por OCR.

## Límites

- **No es infalible.** Puede dejar pasar un dato o marcar de más. Revisa siempre el resultado.
- El mapa (`.json`) que permite restaurar el documento guarda los datos reales. Guárdalo en tu equipo y no lo compartas.

## Usarlo desde el código

```bash
pip install pymupdf
python app.py
```

Pruebas:

```bash
python prueba.py
python prueba_pdf.py
```

Para generar de nuevo el `.exe` y la carpeta `USB\`: doble clic en `empaquetar.bat` (necesita Python 3.9+ e internet la primera vez).

| Archivo | Qué hace |
|---|---|
| `anonimizador.py` | Detección y reemplazo de datos |
| `pdf_anon.py` | Borrado de datos en PDF |
| `app.py` | Interfaz web local |
| `empaquetado/` | Icono e instalador del acceso directo |

Todos los datos de las pruebas son ficticios.

## Licencia

[AGPL-3.0](LICENSE). El ejecutable incluye [PyMuPDF](https://github.com/pymupdf/PyMuPDF), que se distribuye bajo AGPL-3.0.
