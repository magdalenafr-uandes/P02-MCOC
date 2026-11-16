"""Genera la presentación PDF a partir de la evidencia verificada de defensa."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

RAIZ = Path(__file__).resolve().parents[2]
EVIDENCIA = RAIZ / "proyecto/docs/evidencia_defensa"
FIGURAS = Path(__file__).resolve().parent / "figuras"
SALIDA = RAIZ / "Defensa final/Defensa final - Grupo 1.pdf"
W, H = 960, 540
TINTA = "#172b3a"
SEC = "#4d6576"
ACENTO = "#0a7168"
FONDO = "#f7faf9"
ROJO = "#a44436"
NOMBRES = {
    "unica": "Continua · activación conjunta",
    "continua": "Continua · activación sucesiva",
    "espera_3h": "Espera 3 h",
    "espera_6h": "Espera 6 h",
    "unica_manta": "Continua conjunta + manta",
    "continua_manta": "Continua sucesiva + manta",
    "espera_3h_manta": "Espera 3 h + manta",
    "espera_6h_manta": "Espera 6 h + manta",
    "unica_poliestireno": "Continua conjunta + poliestireno",
    "continua_poliestireno": "Continua sucesiva + poliestireno",
}


def numero(x, n=2):
    return f"{float(x):.{n}f}".replace(".", ",")


def filas_csv(nombre):
    with (EVIDENCIA / nombre).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Presentacion:
    def __init__(self):
        fuentes = [
            (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", "segoeui.ttf", "segoeuib.ttf"),
            (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        ]
        carpeta, regular, negrita = next(
            (r, a, b) for r, a, b in fuentes if (r / a).is_file() and (r / b).is_file()
        )
        pdfmetrics.registerFont(TTFont("Defensa", str(carpeta / regular)))
        pdfmetrics.registerFont(TTFont("Defensa-Bold", str(carpeta / negrita)))
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        self.c = Canvas(str(SALIDA), pagesize=(W, H))
        self.c.setTitle("Defensa final de P02-MCOC · Grupo 1")
        self.c.setAuthor("Juan Pablo Cáceres, Magdalena Fernández, Mauricio Lenz")
        self.n = 0

    def texto(self, contenido, x, y, tam=18, color=TINTA, negrita=False, ancho=860):
        fuente = "Defensa-Bold" if negrita else "Defensa"
        self.c.setFont(fuente, tam)
        self.c.setFillColor(HexColor(color))
        for bloque in contenido.splitlines():
            linea = ""
            for palabra in bloque.split():
                candidato = f"{linea} {palabra}".strip()
                if linea and self.c.stringWidth(candidato, fuente, tam) > ancho:
                    self.c.drawString(x, y, linea)
                    y -= tam * 1.25
                    linea = palabra
                else:
                    linea = candidato
            self.c.drawString(x, y, linea)
            y -= tam * 1.25
        return y

    def pagina(self, titulo, seccion):
        self.n += 1
        self.c.setFillColor(HexColor(FONDO))
        self.c.rect(0, 0, W, H, stroke=0, fill=1)
        self.texto(seccion.upper(), 45, 505, 12, ACENTO, True)
        self.texto(titulo, 45, 459, 33, TINTA, True, 885)
        self.c.setStrokeColor(HexColor("#c8d7d9"))
        self.c.line(45, 42, 915, 42)
        self.texto(f"P02-MCOC   /   GRUPO 1                                      {self.n:02d}", 45, 23, 10, SEC)

    def parrafo(self, titulo, contenido, x, y, ancho=410):
        y = self.texto(titulo, x, y, 19, ACENTO, True, ancho)
        return self.texto(contenido, x, y - 8, 18, TINTA, ancho=ancho) - 25

    def figura(self, archivo, x, y, w, h):
        im = ImageReader(str(archivo))
        ix, iy = im.getSize()
        escala = min(w / ix, h / iy)
        self.c.drawImage(im, x + (w - ix * escala) / 2, y + (h - iy * escala) / 2,
                         ix * escala, iy * escala, mask="auto")

    def tabla(self, encabezados, datos, x, y, anchuras, alto=30, fuente=14):
        self.c.setFillColor(HexColor(TINTA))
        self.c.rect(x, y, sum(anchuras), alto, stroke=0, fill=1)
        self.c.setFont("Defensa-Bold", fuente)
        self.c.setFillColor(white)
        xx = x
        for celda, ancho in zip(encabezados, anchuras):
            self.c.drawString(xx + 8, y + (alto - fuente) / 2 + 2, celda)
            xx += ancho
        for i, fila in enumerate(datos):
            yy = y - (i + 1) * alto
            self.c.setFillColor(HexColor("#ffffff" if i % 2 == 0 else "#eaf2f1"))
            self.c.rect(x, yy, sum(anchuras), alto, stroke=0, fill=1)
            xx = x
            for celda, ancho in zip(fila, anchuras):
                self.texto(celda, xx + 8, yy + (alto - fuente) / 2 + 2, fuente, ancho=ancho - 14)
                xx += ancho

    def fin(self):
        self.c.showPage()


def main():
    estado = json.loads((EVIDENCIA / "estado.json").read_text(encoding="utf-8"))
    if estado["faltantes"]:
        raise ValueError("La presentación final requiere la comparación completa.")
    nivel = estado["nivel_principal"]
    agregadas = filas_csv("comparacion.csv")
    escenario = filas_csv("escenarios.csv")
    cribado = {r["plan"]: r for r in agregadas if r["nivel"] == nivel and r["pesos"] == "curvas"}
    refinadas = {r["plan"]: r for r in agregadas if r["nivel"] == "fino" and r["pesos"] == "curvas"}
    aptas = [r for r in refinadas.values() if r["cumple"] == "si"]
    elegida = min(aptas, key=lambda r: float(r["D_h"])) if aptas else None
    provisionales = [r for r in cribado.values() if r["cumple"] != "no" and r["plan"] not in refinadas]
    if elegida and any(float(r["D_h"]) <= float(elegida["D_h"]) for r in provisionales):
        elegida = None
    resultado = (
        f"{NOMBRES[elegida['plan']]} cumple en {numero(elegida['D_h'])} h."
        if elegida else (
            "La decisión queda pendiente de refinamiento."
            if provisionales else "Ninguna alternativa evaluada cumple los dos límites."
        )
    )
    sha = estado.get("commit_modelo") or subprocess.check_output(
        ["git", "-C", str(RAIZ), "rev-parse", "HEAD"], text=True
    ).strip()
    deck = Presentacion()

    deck.pagina("Control térmico en la fundación de Taltal", "Decisión · 0:30")
    deck.texto(resultado, 45, 373, 37, ACENTO, True, 830)
    deck.texto("Menor tiempo de colocación con hasta 5% de excedencia conjunta en el modelo de escenarios.",
               45, 249, 24, ancho=810)
    deck.texto("636,8 m³ de hormigón · 15,92 h como mínimo físico supuesto · 14 días de evaluación",
               45, 161, 19, SEC, ancho=820)
    deck.texto("Juan Pablo Cáceres   ·   Magdalena Fernández   ·   Mauricio Lenz", 45, 91, 17)
    deck.texto("Grupo 1 · Defensa del 19 de noviembre de 2026", 45, 66, 14, SEC)
    deck.fin()

    deck.pagina("Una mezcla identificada, dos curvas M1", "Datos · 0:50")
    deck.figura(RAIZ / "proyecto/results/figures/fuente_calor_medida.png", 40, 114, 680, 308)
    y = deck.parrafo("Calor por edad", "M1_SS integra 88,1 MJ/m³ y M1_22A integra 61,2 MJ/m³.", 731, 376, 185)
    deck.parrafo("Clima", "Tres bloques ERA5 del sitio. Pronóstico del 16 de noviembre como contraste.", 731, y, 185)
    deck.texto("Ocho curvas trazables. Se conserva M1 del IFC y se condiciona la evaluación a ese rótulo.",
               47, 82, 15, SEC)
    deck.fin()

    deck.pagina("La colocación cambia el dominio térmico", "Física y método · 1:05")
    a = deck.parrafo("Balance físico", "ρ cₚ ∂T/∂t = div(k grad T) + Q(a). Fuente en W/m³, edad a desde cada activación y colocación a 18 °C.", 45, 392)
    a = deck.parrafo("Bordes e interfaces", "Suelo explícito, base fija, intercambio con viento y radiación. La cara cubierta pasa a contacto conductivo con la nueva vertida.", 45, a)
    b = deck.parrafo("Celdas y avance explícito", "Capacidad ρ cₚ V por voxel. El paso se limita por C/ΣG y por los eventos del cronograma.", 500, 392)
    deck.parrafo("Diferencial global", "Extremos simultáneos de hormigón activo. A 25 mm se interpola entre cara y centro; la malla gruesa no resuelve esa profundidad.", 500, b)
    deck.texto("Criterios docentes   T máxima ≤ 70 °C   /   diferencial ≤ 20 °C   /   horizonte base de 336 h",
               45, 79, 17, ACENTO, True)
    deck.fin()

    deck.pagina("Cada escenario aporta una sola falla", "Probabilidad · 0:55")
    deck.texto("2 curvas M1 × 3 historias ERA5 = 6 escenarios por alternativa.", 45, 389, 24, ACENTO, True)
    deck.parrafo("Pesos", "M1_SS 75% y M1_22A 25%. Cada historia aporta un tercio. El producto supone independencia.", 45, 326)
    deck.parrafo("Evento conjunto", "Una falla cuenta una vez si T máxima > 70 °C, si el diferencial supera 20 °C o si ocurre ambas cosas.", 500, 326)
    ejemplo = next(r for r in escenario if (r["plan"], r["nivel"], r["curva"], r["clima"])
                   == ("unica", nivel, "M1_SS", "era5_2025"))
    deck.tabla(("Ejemplo real", "Peso", "T máxima", "Diferencial", "Falla"),
               [("Única · SS · ERA5 2025", "25%", numero(ejemplo["T_max_C"]) + " °C",
                 numero(ejemplo["delta_C"]) + " °C", ejemplo["I_F"])],
               45, 158, (310, 115, 147, 153, 145), 40, 17)
    deck.texto("La menor fila pesa 8,33%. Un solo escenario con falla ya supera el umbral de 5%.",
               45, 76, 17, SEC)
    deck.fin()

    deck.pagina("Tiempo y riesgo para los mismos recursos", "Comparación · 1:10")
    deck.tabla(("Alternativa", "D [h]", "P(T)", "P(Δ)", "P conjunta"),
               [(NOMBRES[p], numero(r["D_h"]), numero(float(r["P_T"]) * 100, 0) + "%",
                 numero(float(r["P_delta"]) * 100, 0) + "%", numero(float(r["P_F"]) * 100, 0) + "%")
                for p, r in ((p, cribado[p]) for p in NOMBRES)],
               44, 382, (250, 67, 60, 60, 89), 28, 12)
    deck.figura(FIGURAS / "duracion_riesgo.png", 575, 118, 347, 245)
    dz = "0,10" if nivel == "barrido" else "0,05"
    deck.texto(f"Malla 0,50 × 0,50 × {dz} m. Una línea de 40 m³/h. P observada sirve de cota si el horizonte sigue abierto.",
               45, 65, 14, SEC)
    deck.fin()

    deck.pagina("El diferencial identifica el mecanismo crítico", "Evolución térmica · 1:10")
    deck.figura(FIGURAS / "curvas_comparadas.png", 36, 92, 888, 319)
    deck.texto("Activación conjunta · M1_SS · ERA5 2025. Extremos simultáneos; con protección el horizonte sigue abierto.",
               45, 65, 15, SEC)
    deck.fin()

    deck.pagina("El corte ubica la zona más caliente", "Comprobación · 0:40")
    deck.figura(FIGURAS / "corte_critico.png", 40, 76, 608, 316)
    y = deck.parrafo("Escenario", "Vertida única sin manta, M1_SS y análogo 2025. Corte al instante del mayor diferencial.", 667, 371, 244)
    deck.parrafo("Qué verificar en obra", "Emparejar sensores de núcleo y superficie. Registrar también el ambiente y los eventos de colocación y protección.", 667, y, 244)
    deck.fin()

    deck.pagina("Decisión y control en obra", "Cierre · 0:40")
    deck.texto(resultado, 45, 367, 32, ACENTO, True, 850)
    y = deck.parrafo("Próxima decisión", "Confirmar recursos y material. Evaluar una protección que cubra las zonas frías persistentes, con los mismos casos climáticos.", 45, 278)
    deck.parrafo("Contingencia", "Si hay desviación, comprobar sensores y ambos indicadores antes de ajustar la siguiente colocación o el retiro de protección.", 498, 278)
    deck.texto("El riesgo está condicionado a las curvas, historias y pesos declarados.", 45, min(100, y), 17, SEC)
    deck.fin()

    deck.pagina("Cómo se comprobó el resultado numérico", "Respaldo · verificación")
    control = [r for r in escenario if (r["plan"], r["curva"], r["clima"]) == ("unica", "M1_SS", "era5_2025")]
    deck.tabla(("Nivel", "T máx [°C]", "Δ máx [°C]", "Horizonte [h]"),
               [(r["nivel"], numero(r["T_max_C"], 3), numero(r["delta_C"], 3), r["horizonte_h"])
                for r in control], 45, 353, (220, 176, 176, 200), 37, 15)
    deck.texto("Comparar cribado–fino para espacio, cribado–temporal para paso y cribado–registro para muestreo. "
               "El caso adiabático reproduce la curva de hidratación a partir de la energía integrada.", 45, 135, 18, ancho=840)
    deck.fin()

    deck.pagina("Cronogramas y límites de la búsqueda", "Respaldo · construcción")
    deck.figura(FIGURAS / "cronogramas.png", 45, 182, 870, 232)
    deck.texto("Una línea a 40 m³/h, sin simultaneidad. Esperas por interfaz: 0, 3 y 6 h. "
               "Las protecciones no cambian la duración física. Diez planes, seis escenarios por plan.",
               45, 135, 19, ancho=850)
    deck.texto("No hay mínimo factible en esta familia. No se demuestra optimalidad global ni se valida una medida aún no simulada.",
               45, 69, 16, SEC, ancho=850)
    deck.fin()

    deck.pagina("Supuestos y alcance de la evidencia", "Respaldo · limitaciones")
    deck.parrafo("Riesgo condicionado", "Con pesos 50/50, P conjunta sigue entre 50% y 100%. Las dos campañas M1 son escenarios de modelo; falta confirmar su comparabilidad.", 45, 389)
    deck.parrafo("Horizonte", "Base 336 h, extensión 420 h. Persisten señales tardías en algunos casos protegidos: P observada es cota inferior, ya mayor que 5%.", 500, 389)
    deck.parrafo("Verificación y validación", "Caso adiabático: error 7,11 × 10⁻¹⁵ °C. Balance relativo < 3 × 10⁻¹⁶ en referencias. No hay mediciones independientes de la fundación.", 45, 222)
    deck.parrafo("Datos de obra", "Capacidad, protecciones y pesos son supuestos docentes. Confirmarlos antes de ampliar la familia o recomendar ejecución. El criterio térmico no calcula fisuración.", 500, 222)
    deck.fin()

    deck.pagina("Datos y reproducción sin internet", "Respaldo · fuentes")
    deck.parrafo("Entradas versionadas", "IFC oficial, fuente Q(t), tres archivos ERA5 con metadatos, configuración de escenarios y pesos, y cronogramas.", 45, 392)
    deck.parrafo("Resultados", "Las filas por escenario contienen máximos, ubicación y balance. La tabla de comparación incluye la sensibilidad de pesos 50/50.", 500, 392)
    deck.texto(f"Evidencia congelada en Git   {sha}", 45, 224, 15, ACENTO, True)
    deck.texto("Rama: codex/defensa-final · github.com/magdalenafr-uandes/P02-MCOC", 45, 195, 16)
    deck.texto("Caso: defensa.py --nivel barrido --plan unica --curva M1_SS --clima era5_2025", 45, 155, 16)
    deck.texto("Comparación: defensa.py --nivel barrido --procesos 3", 45, 122, 16)
    deck.texto("Ejecutar desde raíz con proyecto/.venv/Scripts/python.exe proyecto/scripts/…", 45, 92, 14, SEC)
    deck.texto("Fuentes: IFC y archivo del curso · Open-Meteo ERA5 · Guía técnica en proyecto/docs/defensa.md", 45, 69, 14, SEC)
    deck.fin()
    deck.c.save()
    print(SALIDA)


if __name__ == "__main__":
    main()
