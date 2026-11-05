"""El mapa del código no debe apuntar a marcadores que ya no existen."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MAPA = RAIZ / "MAPA_DEL_CODIGO.md"
SRC = RAIZ / "src" / "mcplan"


def _etiquetas_en_codigo() -> dict[str, list[Path]]:
    encontradas: dict[str, list[Path]] = {}
    for archivo in SRC.rglob("*.py"):
        for tag in re.findall(r"#\s*\[MAPA:([A-Za-z0-9-]+)\]", archivo.read_text(encoding="utf-8")):
            encontradas.setdefault(tag, []).append(archivo)
    return encontradas


def test_cada_etiqueta_del_mapa_existe_en_el_codigo():
    citadas = set(re.findall(r"MAPA:([A-Za-z0-9-]+)", MAPA.read_text(encoding="utf-8")))
    en_codigo = _etiquetas_en_codigo()
    faltan = sorted(citadas - set(en_codigo))
    assert not faltan, f"El mapa cita etiquetas inexistentes: {faltan}"


def test_etiquetas_unicas_y_documentadas():
    en_codigo = _etiquetas_en_codigo()
    repetidas = {t: [str(p) for p in ps] for t, ps in en_codigo.items() if len(ps) > 1}
    assert not repetidas, f"Etiquetas repetidas: {repetidas}"
    citadas = set(re.findall(r"MAPA:([A-Za-z0-9-]+)", MAPA.read_text(encoding="utf-8")))
    sin_mapa = sorted(set(en_codigo) - citadas)
    assert not sin_mapa, f"Etiquetas en el código que el mapa no menciona: {sin_mapa}"
