from anonimizador import anonimizar, restaurar
T = """Bogotá, 12 de octubre de 2026

Señora Marta Lucía Gómez Rivas, identificada con C.C. 52.123.456, de FAE-2026-0731.
Dirección: Carrera 80C # 65F-58 Sur, Bogotá. Teléfono 310 555 0147 o +57 300 111 2233.
Correo: marta.gomez@correo.com. NIT de la entidad 830.101.258-8.
El afiliado Carlos Andrés Peña Rueda pagó $1.350.000 en la cuenta de ahorros 123456789012.
Marta Lucía Gómez Rivas solicita revisión. La Sra. Gómez Rivas adjunta cédula 1012345678.
El canon es de 1.500.000 pesos y el radicado del proceso 11001-40-03-099-2026-00123-00.

Atentamente,
Julián Andrés Torres Mejía
"""
s, mapa, inf = anonimizar(T)
print(s); print(inf)
assert "52.123.456" not in s and "310 555 0147" not in s and "marta.gomez" not in s
assert "830.101.258-8" not in s and "Carlos Andrés" not in s and "Gómez Rivas" not in s
assert "1012345678" not in s and "Carrera 80C" not in s and "1.350.000" not in s
assert "FAE-2026-0731" not in s and "123456789012" not in s
assert "Julián" not in s
assert "1.500.000 pesos" in s, "valor sin $ no debe tomarse como cédula"
r = restaurar(s, mapa)
assert "[" not in r.replace("[", "", 0) or "_" not in r, "no deben quedar marcadores"
assert "52.123.456" in r and "Marta Lucía Gómez Rivas" in r and "310 555 0147" in r
assert "Sra. Marta Lucía Gómez Rivas" in r  # la variante vuelve como nombre completo
print("OK")

# Nombres: segundo apellido, «de la», mayúsculas, guion y bloques de firma.
casos = {
    "Señora Marta Gómez presentó la queja. Marta Gómez Rivas firma el acta.": ["Rivas", "Gómez"],
    "Señora María José de la Hoz Rivas solicita revisión.": ["Hoz", "Rivas"],
    "Señor Juan Pablo del Castillo Pérez Gómez pide copia.": ["Castillo", "Gómez"],
    "Señora Marta Gómez Rivas.\nAtentamente,\n\nMARTA GÓMEZ RIVAS\nC.C. 52.123.456": ["MARTA", "RIVAS"],
    "Firma: Ana Ruiz Díaz": ["Ruiz", "Díaz"],
    "Proyectó: Luisa Fernanda Ortiz Cárdenas\nRevisó: Pedro Nel Rojas Vélez": ["Ortiz", "Vélez"],
    "Doctora Ángela Pérez-Gómez Ruiz": ["Pérez", "Ruiz"],
    "_____________\nLUISA ORTIZ CÁRDENAS\nRepresentante Legal": ["LUISA", "CÁRDENAS"],
}
for texto, prohibidas in casos.items():
    s = anonimizar(texto)[0]
    for p in prohibidas:
        assert p not in s, f"quedó «{p}» en: {s!r}"
s = anonimizar("Señora Marta Gómez Gerente General de la empresa y de la junta.")[0]
assert "Gerente General de la empresa y de la junta" in s, s  # ni el cargo ni «de la» se tocan
print("OK nombres")
