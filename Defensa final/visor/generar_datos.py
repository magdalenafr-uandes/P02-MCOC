"""Regenera datos.js desde la evidencia incluida en el repositorio."""
import csv
import json
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
DOCS = HERE.parents[1] / "proyecto" / "docs"
CAMPAIGNS = {
    "original": "evidencia_defensa",
    "extension": "evidencia_extension_defensa",
    "pilotos": "evidencia_extension_pilotos",
}
FIELDS = (
    "plan", "nivel", "curva", "clima", "D_h", "T_max_C", "t_T_h",
    "delta_C", "t_delta_h", "horizonte_h", "pico_tardio", "I_F",
    "punto_caliente", "punto_frio", "clave",
)


def table(folder, filename):
    with (folder / filename).open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


data = {}
for campaign, name in CAMPAIGNS.items():
    folder = DOCS / name
    runs = []
    with ZipFile(folder / "corridas.zip") as archive:
        for filename in sorted(archive.namelist()):
            result = json.loads(archive.read(filename))
            row = {field: result[field] for field in FIELDS}
            row["series"] = {
                key: [round(value, 5) for value in values]
                for key, values in result["series"].items()
            }
            runs.append(row)
    data[campaign] = {
        "runs": runs,
        "comparison": table(folder, "comparacion.csv"),
    }

data["schedule"] = table(DOCS / CAMPAIGNS["original"], "cronogramas.csv")
(HERE / "datos.js").write_text(
    "window.EVIDENCIA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
    encoding="utf-8",
)
