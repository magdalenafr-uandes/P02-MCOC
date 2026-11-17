"""Construye la guía de la defensa a partir de los datos archivados. Requiere ReportLab."""
from csv import DictReader
from datetime import datetime
from json import loads
from math import isfinite
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'proyecto'
BASE = PROJECT / 'docs/evidencia_defensa'
EXT = PROJECT / 'docs/evidencia_extension_defensa'
PILOTS = PROJECT / 'docs/evidencia_extension_pilotos'
OUTPUT = ROOT / 'Guía de la entrega final/P02-MCOC - Guía visual de la entrega final.pdf'
REPO = 'https://github.com/magdalenafr-uandes/P02-MCOC'
DEFENSE = 'baacb33600a3d11a4634d9f9192bf2d1a03b290e'
W, H = A4
L = 41
CW = W - 2 * L

PAPER = '#F6F5EF'
WHITE = '#FFFFFF'
INK = '#182921'
MUTED = '#43574E'
TEAL = '#136554'
MINT = '#DFEDE2'
LINE = '#CFD8CE'
DARK = '#16382E'
GOLD = '#F1D28A'
AMBER = '#7F511B'
CREAM = '#F7EBD3'
RED = '#9C4736'


def register_fonts():
    windows = Path('C:/Windows/Fonts')
    if windows.is_dir():
        font_files = ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'consola.ttf')
    else:
        windows = Path('/usr/share/fonts/truetype/dejavu')
        font_files = ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSerif.ttf', 'DejaVuSansMono.ttf')
    for name, file in zip(('Body', 'Bold', 'Title', 'Mono'), font_files):
        pdfmetrics.registerFont(TTFont(name, str(windows / file)))
    pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold', italic='Body', boldItalic='Bold')


def csv_rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(DictReader(stream))


def number(value, digits=2):
    return f'{float(value):.{digits}f}'.replace('.', ',')


def hour(value):
    return datetime.fromisoformat(value).strftime('%H:%M')


def snapshot(path):
    return f'{REPO}/blob/{DEFENSE}/{path}'


class Guide:
    def __init__(self):
        self.c = Canvas(str(OUTPUT), pagesize=A4, pageCompression=1, invariant=1)
        self.c.setTitle('P02-MCOC | Guía visual de la entrega final')
        self.c.setAuthor('Grupo 1 | P02-MCOC')
        self.c.setSubject('Resultados, pruebas y entregables de la defensa y de F01')

    def rect(self, x, y, w, h, bg, border=None, radius=0):
        self.c.setFillColor(bg)
        if border:
            self.c.setStrokeColor(border)
        if radius:
            self.c.roundRect(x, H - y - h, w, h, radius, fill=1, stroke=bool(border))
        else:
            self.c.rect(x, H - y - h, w, h, fill=1, stroke=bool(border))

    def line(self, x, y, x2, y2, color=LINE, width=.7, dash=()):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(width)
        self.c.setDash(dash)
        self.c.line(x, H - y, x2, H - y2)
        self.c.setDash()

    def dot(self, x, y, r, color):
        self.c.setFillColor(color)
        self.c.circle(x, H - y, r, fill=1, stroke=0)

    def text(self, value, x, y, size=11, font='Body', color=INK, align='left'):
        self.c.setFillColor(color)
        self.c.setFont(font, size)
        if align == 'right':
            self.c.drawRightString(x, H - y - size, str(value))
        elif align == 'center':
            self.c.drawCentredString(x, H - y - size, str(value))
        else:
            self.c.drawString(x, H - y - size, str(value))

    def p(self, value, x, y, w, size=11, color=INK, leading=None):
        leading = leading or size * 1.34
        style = ParagraphStyle('block', fontName='Body', fontSize=size, leading=leading,
                               alignment=TA_LEFT, textColor=colors.HexColor(color))
        paragraph = Paragraph(value, style)
        _, height = paragraph.wrap(w, H)
        assert y + height <= H - 34, (y, value)
        paragraph.drawOn(self.c, x, H - y - height)
        return y + height

    def link(self, label, url, x, y, size=10, color=TEAL):
        self.text(label, x, y, size, 'Bold', color)
        width = pdfmetrics.stringWidth(label, 'Bold', size)
        self.line(x, y + size + 2, x + width, y + size + 2, color, .45)
        self.c.linkURL(url, (x, H-y-size-3, x+width, H-y+1), relative=0)

    def header(self, n, tag, title, subtitle):
        self.c.bookmarkPage(f'p{n}')
        self.c.addOutlineEntry(title, f'p{n}')
        self.rect(0, 0, W, H, PAPER)
        self.line(L, 30, W - L, 30, TEAL, 1.2)
        self.text(tag.upper(), L, 43, 9, 'Bold', TEAL)
        self.text(title, L, 62, 29, 'Title')
        return self.p(subtitle, L, 109, CW, 11.4, MUTED)

    def footer(self, n, source):
        self.line(L, 785, W - L, 785)
        self.text(source, L, 796, 8, color=MUTED)
        self.text(f'{n:02d} / 12', W - L, 795, 9, 'Bold', TEAL, 'right')
        self.c.showPage()

    def note(self, x, y, w, h, title, body, bg=MINT, accent=TEAL, size=10.5):
        self.rect(x, y, w, h, bg, radius=6)
        self.rect(x, y + 8, 3, h - 16, accent)
        self.text(title, x + 13, y + 9, 11.6, 'Bold', accent)
        end = self.p(body, x + 13, y + 29, w - 26, size)
        assert end <= y + h - 5, (title, end, y + h)

    def subhead(self, value, y, x=L):
        self.text(value, x, y, 14, 'Bold', TEAL)

    def table(self, y, labels, widths, rows, height=26, x=L, size=10, accent_rows=()):
        w = sum(widths)
        self.rect(x, y, w, 27, DARK, radius=4)
        left = x
        for label, width in zip(labels, widths):
            assert pdfmetrics.stringWidth(label, 'Bold', 9) < width - 12, label
            self.text(label, left + 8, y + 7, 9, 'Bold', WHITE)
            left += width
        for i, row in enumerate(rows):
            top = y + 27 + i * height
            bg = MINT if i in accent_rows else WHITE if i % 2 == 0 else '#EEEEE7'
            self.rect(x, top, w, height, bg)
            left = x
            for value, width in zip(row, widths):
                end = self.p(escape(str(value)), left + 8, top + 5, width - 15, size)
                assert end <= top + height - 1, (value, end, top, height)
                left += width
        return y + 27 + len(rows) * height

    def picture(self, path, x, y, max_w, max_h):
        im = ImageReader(str(path))
        width, height = im.getSize()
        factor = min(max_w / width, max_h / height)
        width, height = width * factor, height * factor
        self.c.drawImage(im, x + (max_w - width) / 2, H-y-height, width, height, mask='auto')
        return y + height

    def cover(self):
        self.c.bookmarkPage('p1')
        self.c.addOutlineEntry('Resumen de la decisión', 'p1')
        self.rect(0, 0, W, H, PAPER)
        self.rect(0, 0, W, 426, DARK)
        self.line(L, 42, W - L, 42, '#A1BDAD', .8)
        self.text('P02-MCOC   /   GRUPO 1', L, 57, 10, 'Bold', '#D2E4D8')
        self.text('17 NOV 2026', W-L, 57, 10, 'Bold', '#D2E4D8', 'right')
        self.text('Guía visual de la', L, 96, 42, 'Title', WHITE)
        self.text('entrega final', L, 146, 42, 'Title', WHITE)
        self.p('La decisión térmica, las pruebas que la respaldan y lo que el grupo debe entregar.',
               L+1, 212, 455, 14, '#D7E8DF')
        self.rect(L, 269, CW, 117, '#254B3D', radius=7)
        self.text('CANDIDATO PARA LA DEFENSA', L+15, 282, 9, 'Bold', '#D5E4D8')
        self.text('Colocación continua a 12 °C y EPS de 20 cm', L+15, 306, 19, 'Bold', WHITE)
        self.p('Seis escenarios sin excedencias en malla fina. La comprobación más fina deja un margen de <b>0,18 °C</b> frente al límite diferencial.',
               L+15, 341, CW-30, 11.5, '#E8F0EA')

        gap = 9
        width = (CW - 3 * gap) / 4
        panels = [('15,92 h', 'Tiempo de colocación', '40 m³/h supuestos'),
                  ('49,64 °C', 'Máxima en malla fina', 'Límite 70 °C'),
                  ('19,82 °C', 'Diferencial a 0,20 m', 'Límite 20 °C'),
                  ('0 de 6', 'Excedencias', 'Malla fina de 0,25 m')]
        for i, (value, label, sub) in enumerate(panels):
            x = L + i * (width + gap)
            self.rect(x, 443, width, 81, MINT if i != 2 else CREAM, radius=5)
            self.text(value, x+9, 451, 22, 'Title', DARK if i != 2 else AMBER)
            self.text(label, x+9, 484, 8.2, 'Bold')
            self.text(sub, x+9, 501, 8.2, color=MUTED)

        self.subhead('Dónde encontrar cada tema', 550)
        contents = [(2, 'Cronograma y geometría'), (3, 'Hidratación y clima'), (4, 'Modelo y límites'),
                    (5, 'Probabilidad y seis escenarios'), (6, 'Comparación de diez planes'),
                    (7, 'Sensibilidad del candidato'), (8, 'Picos, curvas y ubicaciones'),
                    (9, 'Pruebas y evidencia archivada'), (10, 'Controles y preguntas'),
                    (11, 'Entregables y fechas'), (12, 'Reproducción y fuentes')]
        for i, (n, label) in enumerate(contents):
            x = L + (i // 6) * (CW / 2 + 11)
            t = 580 + (i % 6) * 24
            self.text(f'{n:02d}', x, t, 9, 'Bold', TEAL)
            self.text(label, x+25, t-2, 11, 'Bold')
            self.c.linkRect('', f'p{n}', (x, H-t-17, x+240, H-t+3), relative=0, thickness=0)
        self.p('Guía de consulta para el grupo. El PDF de exposición y el artículo F01 son las piezas de entrega.',
               L, 734, CW, 10, MUTED)
        self.footer(1, 'Lectura rápida  /  Cifras redondeadas para comunicar')

    def schedule(self, stages):
        self.header(2, 'Geometría y cronograma', '636,775 m³ en cinco sólidos',
                    'Fundación del Parque Eólico Wayra, Taltal. Inicio común el jueves 19 de noviembre, 04:00 hora de Santiago; una línea de 40 m³/h y sin simultaneidad, como supuestos.')
        self.subhead('Tiempo hasta terminar de colocar', 160)
        x0 = L + 113
        axis = CW - 147
        for mark in (0, 10, 20, 30, 40):
            x = x0 + mark * axis / 40
            self.line(x, 195, x, 319)
            self.text(mark, x, 321, 8.5, color=MUTED, align='center')
        bar_colors = [TEAL, '#367B69', '#508A78', '#68A18D', '#89B5A5']
        for i, wait in enumerate((0, 3, 6)):
            y = 203 + i * 39
            label = 'Continua' if wait == 0 else f'{wait} h por interfaz'
            self.text(label, L, y+1, 10.5, 'Bold')
            for j, row in enumerate(stages):
                start = float(row['inicio_h']) + wait * j
                length = float(row['duracion_h'])
                self.rect(x0 + start * axis/40, y, length * axis/40, 17, bar_colors[j])
                if wait and j < len(stages)-1:
                    self.rect(x0 + (start+length) * axis/40, y + 6, wait * axis/40, 5, GOLD)
            end = float(stages[-1]['fin_h']) + wait * 4
            self.text(f'{number(end)} h', x0 + end * axis/40 + 7, y + 1, 9, 'Bold', TEAL)
        self.text('Horas desde el inicio común', x0, 340, 9, color=MUTED)
        self.rect(L, 340, 11, 9, GOLD)
        self.text('Espera', L+16, 338, 9, color=MUTED)

        self.subhead('Secuencia física continua', 375)
        rows = [(f'V{r["vertida"]}', number(r['volumen_m3'], 3), hour(r['inicio']),
                 hour(r['fin']), number(r['duracion_h'], 3)) for r in stages]
        self.table(405, ['Tramo IFC', 'Volumen [m³]', 'Inicio', 'Fin', 'Duración [h]'],
                   [94, 120, 93, 90, CW-397], rows, height=28)
        self.note(L, 596, CW, 72, 'El cálculo de 15,92 h',
                  'D = fin de la última vertida − inicio común. Con una línea, D = 636,775 ÷ 40 = 15,919 h si la operación es continua. Las cuatro esperas de 3 h agregan 12 h; las de 6 h, 24 h.')
        self.p('El enfriamiento posterior se informa por separado. La activación conjunta de los cinco sólidos idealiza la edad térmica. La activación sucesiva conserva el mismo cronograma sin esperas.',
               L, 689, CW, 11, MUTED)
        self.footer(2, 'Fuente  /  IFC versionado, defensa.yaml y cronogramas.csv')

    def inputs(self, hydration):
        self.header(3, 'Insumos', 'Hidratación y clima',
                    'Cada corrida usa una curva completa de calor y un bloque horario completo de clima. El material del IFC se identifica como M1.')
        self.subhead('Las ocho curvas de fuente volumétrica Q', 152)
        self.rect(L, 180, CW, 256, WHITE, radius=6)
        x0, y0, x1, y1 = L+47, 396, W-L-19, 208
        data_max = max(v for row in hydration for v in row[1:] if isfinite(v))
        scale = 100 * (int(data_max / 100) + 1)
        hours = float(hydration[-1][0])
        for mark in range(0, scale+1, 100):
            y = y0 - mark * (y0-y1)/scale
            self.line(x0, y, x1, y, '#E5EAE4')
            self.text(mark, x0-8, y-5, 8, color=MUTED, align='right')
        for mark in range(0, int(hours)+1, 24):
            x = x0 + mark * (x1-x0)/hours
            self.text(mark, x, y0+6, 8, color=MUTED, align='center')
        self.text('Q [W/m³]', L+10, 188, 9, 'Bold', TEAL)
        self.text('Edad desde inicio de la curva [h]', (x0+x1)/2, 416, 8.8, color=MUTED, align='center')
        curve_colors = ('#126653', '#9DB3A9', '#748D84', '#BAC6B9', '#B56F27', '#BEB09C', '#A89E82', '#D6C5AD')
        for idx in (1, 2, 3, 5, 6, 7, 0, 4):
            path = self.c.beginPath()
            started = False
            for age, *values in hydration:
                value = values[idx]
                if not isfinite(value):
                    started = False
                    continue
                x = x0 + age * (x1-x0)/hours
                y = H - y0 + value * (y0-y1)/scale
                if started:
                    path.lineTo(x, y)
                else:
                    path.moveTo(x, y)
                    started = True
            self.c.setStrokeColor(curve_colors[idx])
            self.c.setLineWidth(2.0 if idx in (0, 4) else .9)
            self.c.setDash((4, 2) if idx >= 4 else ())
            self.c.drawPath(path)
        self.c.setDash()
        for i, (label, color) in enumerate(zip(('M1_SS', 'M2_SS', 'M3_SS', 'M4_SS', 'M1_22A', 'M2_22A', 'M3_22A', 'M4_22A'), curve_colors)):
            x = L + 4 + (i % 4) * 128
            y = 449 + (i // 4) * 16
            self.line(x, y+6, x+16, y+6, color, 1.6, (4, 2) if i >= 4 else ())
            self.text(label, x+22, y, 8.8, 'Bold' if i in (0, 4) else 'Body')

        self.note(L, 493, CW, 99, 'Por qué se usan M1_SS y M1_22A',
                  'Integran <b>88,1</b> y <b>61,2 MJ/m³</b>. Son dos campañas de abril de 2025; el archivo atribuye menor confianza a 22A. La fuente Q se estimó por inversión térmica y comienza 2 h después del inicio del registro. El modelo reinicia la edad por vertida, integra Q con ρcₚ del caso y usa Q = 0 tras el registro. Sin datos para calibrar Arrhenius, se fijó Eₐ = 0.', size=10.1)
        self.note(L, 609, CW, 139, 'Clima congelado del sitio',
                  'ERA5 de <b>2023, 2024 y 2025</b>, vía Open-Meteo y trasladado a las mismas fechas de 2026. Sitio solicitado: −24,95283°, −70,004838°, hora <b>America/Santiago</b>. Bloques de temperatura a 2 m, viento a 10 m y radiación de onda corta (°C, m/s, W/m²).<br/><br/>Horizonte inicial <b>336 h (14 días)</b>; hasta 420 h en la base y 672 h en la extensión si quedan picos tardíos. Pronóstico del 16-nov con cola ERA5 2025 como contraste de peso cero.', bg=WHITE, size=10.1)
        self.footer(3, 'Fuentes  /  source_terms.txt, metadatos de hidratación y snapshots meteorológicos')

    def physics(self):
        self.header(4, 'Modelo térmico', 'Qué se calcula y dónde',
                    'La hidratación aporta calor. La conducción lo redistribuye. El aire, las protecciones y el suelo determinan el intercambio en cada cara.')
        self.rect(L, 158, CW, 252, WHITE, radius=6)
        self.text('CORTE ESQUEMÁTICO DE UNA ZONA DE LA FUNDACIÓN', L+16, 170, 8.6, 'Bold', TEAL)
        x, y = L+45, 239
        self.rect(x-20, y+94, 276, 40, '#DCC9A3')
        self.rect(x, y, 236, 94, '#D3DDD0', border='#91A69B')
        self.rect(x-8, y-8, 252, 8, TEAL)
        self.rect(x-8, y, 8, 94, TEAL)
        self.rect(x+236, y, 8, 94, TEAL)
        self.line(x, y+47, x+236, y+47, '#A8B8AB', .9, (4, 3))
        self.dot(x+129, y+34, 5, RED)
        self.dot(x+12, y+73, 5, '#4D7884')
        self.line(x+129, y+34, x+241, y+34, RED, .8)
        self.line(x+241, y+34, x+257, y+24, RED, .8)
        self.line(x+12, y+73, x+246, y+73, '#4D7884', .8)
        self.text('Calor de hidratación', x+93, y+7, 8.9, 'Bold')
        self.text('Contacto con suelo', x+63, y+104, 9.5, 'Bold')
        self.text('EPS superior y lateral', x+258, y-24, 9.7, 'Bold', TEAL)
        self.text('Núcleo caliente', x+261, y+12, 9.7, 'Bold', RED)
        self.text('Cerca de la superficie', x+251, y+62, 9.7, 'Bold', '#365F6A')
        self.text('a ~25 mm de la cara', x+251, y+76, 9.2, color=MUTED)
        self.text('Al aire: convección por viento, radiación y resistencias de protección.', L+16, 385, 9.3, color=MUTED)

        self.note(L, 428, CW, 123, 'Balance físico y paso numérico',
                  '<b>ρcₚ ∂T/∂t = div(k grad T) + Q(a)</b>. El hormigón usa ρ = 2.400 kg/m³, cₚ = 970 J/(kg·K) y k = 2,22 W/(m·K). El suelo está en la malla y su base se fija a 16,6 °C. Las caras cubiertas por otra vertida pasan a conducción entre celdas.<br/><br/>Volúmenes finitos y Euler explícito: sumar flujos y calor por celda, dividir por su capacidad ρcₚV y avanzar con un paso acotado por C/ΣG y por los cambios de etapa.', size=10)
        self.note(L, 572, (CW-12)/2, 155, 'Máxima global · límite 70 °C',
                  'Tomar la temperatura máxima del hormigón ya colocado, buscando sobre todas las ubicaciones e instantes. Las celdas futuras, el aire y el suelo quedan fuera del indicador.', bg=WHITE)
        self.note(L+(CW+12)/2, 572, (CW-12)/2, 155, 'Diferencial global · límite 20 °C',
                  'En cada instante, restar la mínima a ~25 mm de una cara exterior a la máxima del hormigón activo. Después tomar el mayor diferencial. A ~25 mm se interpola cara-centro y se limita al centro si este queda más cerca.', bg=WHITE)
        self.footer(4, 'Fuentes  /  defensa.md, extension_defensa.md, e07_caso_base.yaml y E06')

    def scenarios(self, fine):
        self.header(5, 'Modelo de incertidumbre', 'Cómo se obtiene el 0%',
                    'Dos curvas M1 × tres historias ERA5 producen seis realizaciones por plan. Las ponderaciones se fijaron antes de la comparación.')
        self.table(152, ['Curva', 'Peso material', 'Peso por cada clima', 'Peso por fila (principal)'],
                   [88, 109, 134, CW-331], [('M1_SS', '75%', '1/3', '25%'),
                                             ('M1_22A', '25%', '1/3', '8,33%')], height=24)
        self.p('Hipótesis de independencia material-clima: peso conjunto = peso de curva × peso de clima. En la sensibilidad 50/50, cada fila pesa 1/6. El pronóstico sirve como contraste sin peso.',
               L, 245, CW, 10.3, MUTED)
        self.note(L, 290, CW, 73, 'Una fila fallida cuenta una sola vez',
                  'Falla si supera 70 °C en T máxima <b>o</b> 20 °C en diferencial. La probabilidad conjunta es la suma de pesos de las filas fallidas. El 5% se aplica antes de redondear.')

        self.subhead('EPS 200 mm a 12 °C · activación conjunta en malla fina', 385)
        rows = []
        for r in fine:
            rows.append((r['curva'], r['clima'][-4:], number(r['T_max_C']), number(r['delta_C'], 3),
                         f'{float(r["horizonte_h"]):.0f}', 'No' if r['I_F'] == '0' else 'Sí'))
        self.table(416, ['Curva', 'ERA5', 'T máx. [°C]', 'Δ máx. [°C]', 'Horiz. [h]', 'Falla'],
                   [94, 68, 84, 91, 92, CW-429], rows, accent_rows=(2,))
        self.note(L, 620, CW, 116, 'Alcance del resultado',
                  'En la matriz fina de 0,25 × 0,25 × 0,05 m, <b>P(T) = P(Δ) = P(falla conjunta) = 0%</b> con ambos juegos de pesos. Los seis horizontes cerraron. La cifra describe los escenarios y pesos elegidos. La validez en obra depende de la representatividad climática, el material, los recursos y el error numérico.', bg=CREAM, accent=AMBER)
        self.footer(5, 'Fuente  /  escenarios.csv y comparacion.csv de la campaña extendida')

    def comparison(self, base):
        self.header(6, 'Búsqueda', 'Diez planes base descartados',
                    'A 18 °C inicial, las diez alternativas excedieron el criterio conjunto por el diferencial. Mantuvieron el volumen, la capacidad y los pesos.')
        labels = {'unica': 'Única, sin aislación', 'unica_manta': 'Única + manta 50 mm',
                  'unica_poliestireno': 'Única + EPS 100 mm', 'continua': 'Sucesiva, sin aislación',
                  'continua_manta': 'Sucesiva + manta 50 mm', 'continua_poliestireno': 'Sucesiva + EPS 100 mm',
                  'espera_3h': 'Espera 3 h, sin aislación', 'espera_3h_manta': 'Espera 3 h + manta',
                  'espera_6h': 'Espera 6 h, sin aislación', 'espera_6h_manta': 'Espera 6 h + manta'}
        rows = []
        for name, label in labels.items():
            principal = base[name, 'curvas']
            alternate = base[name, 'pesos_alternativos_curvas']
            rows.append((label, number(principal['D_h']),
                         number(100*float(principal['P_F']), 0)+'%',
                         number(100*float(alternate['P_F']), 0)+'%',
                         principal['escenarios_horizonte_abierto']))
        self.table(156, ['Configuración', 'D [h]', 'P conjunta', 'P con 50/50', 'Abiertos'],
                   [209, 65, 83, 87, CW-444], rows, height=24)
        self.p('P de máxima térmica fue 0% en los diez. Si un horizonte queda abierto, el riesgo observado es una cota inferior. Ya supera el criterio de 5% incluso con pesos 50/50.',
               L, 439, CW, 10, MUTED)
        self.subhead('Qué cambió al preenfriar y aumentar la aislación', 489)
        self.note(L, 522, CW, 91, '12 °C + EPS de 100 mm · descartado',
                  'Pasaba en barrido; al refinar, SS/ERA5 2025 alcanzó <b>20,1498 °C</b> de diferencial. Esa única fila basta para una probabilidad conjunta de <b>al menos 25%</b> con pesos principales (16,67% con 50/50).', bg=CREAM, accent=AMBER)
        self.note(L, 630, CW, 112, '12 °C + EPS de 200 mm · candidato condicionado',
                  'Mantiene 15,92 h, la cota física para una línea al caudal supuesto. Es el candidato con respaldo de seis escenarios finos. Las esperas de 3 h y 6 h tardan más. Los pilotos incluyeron espesores de 100 a 300 mm a 18 °C; el aumento de espesor por sí solo siguió dando excedencias en el piloto SS/ERA5 2024.')
        self.footer(6, 'Fuentes  /  comparación base, pilotos de EPS y campaña extendida')

    def sensitivity(self, confirmation):
        self.header(7, 'Verificación de la decisión', 'El diferencial manda',
                    'En SS/ERA5 2025, la máxima se mantiene cerca de 49,64 °C. El diferencial aumenta a medida que se refina la malla.')
        self.picture(EXT / 'figuras/sensibilidad_numerica.png', L, 147, CW, 243)
        margin = 20 - float(confirmation['delta_C'])
        self.note(L, 413, CW, 84, f'Margen de {number(margin, 3)} °C en una sola corrida',
                  f'Malla 0,20 × 0,20 × 0,05 m. Máxima <b>{number(confirmation["T_max_C"])} °C</b> a las {number(confirmation["t_T_h"])} h y diferencial <b>{number(confirmation["delta_C"], 4)} °C</b> a las {number(confirmation["t_delta_h"])} h. Los valores se alcanzan en instantes distintos.', bg=CREAM, accent=AMBER)
        self.subhead('Qué se verificó y cuál es el siguiente nivel de evidencia', 518)
        self.table(549, ['Comprobación', 'Resultado y alcance'], [174, CW-174], [
            ('Matriz fina a 0,25 m', '6 de 6 sin excedencias; peor Δ = 19,441 °C.'),
            ('Confirmación a 0,20 m', '1 caso SS/ERA5 2025; queda pendiente acotar el error espacial.'),
            ('Activación sucesiva', '6 de 6 sin excedencias en barrido; queda pendiente en fino.'),
            ('Paso y registro en cribado', '18,634 °C de referencia; 18,636 °C en ambas pruebas. El registro también alteró pasos.'),
            ('Pronóstico, peso cero', 'Δ = 18,344 °C en SS. Sirve como contraste.')], height=35, size=9.8)
        self.footer(7, 'Fuente  /  figura de sensibilidad y escenarios de la extensión')

    def profiles(self, case):
        self.header(8, 'Resultados precalculados', 'Dos máximos, dos momentos',
                    'Corrida crítica SS/ERA5 2025 con EPS 200 mm y 12 °C de colocación. Confirmación a 0,20 m horizontal y 0,05 m vertical.')
        self.rect(L, 151, CW, 402, WHITE, radius=6)
        data = case['series']
        days = [hours/24 for hours in data['t_h']]
        self.text('Temperaturas [°C]', L+13, 163, 10.7, 'Bold', TEAL)
        self.line(L+166, 174, L+181, 174, TEAL, 1.7)
        self.text('Máxima del hormigón', L+188, 166, 9)
        self.line(L+308, 174, L+323, 174, '#507A87', 1.6, (4, 2))
        self.text('Mínima a ~25 mm', L+330, 166, 9)
        self.profile_plot(188, 325, tuple(range(0, 71, 10)), days,
                          [(data['T_max_C'], TEAL, ()), (data['T_superficie_min_C'], '#507A87', (4, 2))],
                          70, case['t_T_h']/24, case['T_max_C'])
        self.text('Diferencial simultáneo [°C]', L+13, 363, 10.7, 'Bold', TEAL)
        self.profile_plot(394, 515, (0, 5, 10, 15, 20), days, [(data['delta_C'], TEAL, ())],
                          20, case['t_delta_h']/24, case['delta_C'])
        self.text('Días desde el inicio común', W/2, 539, 8.8, color=MUTED, align='center')

        self.table(577, ['Indicador', 'Momento', 'Ubicación en la corrida crítica'],
                   [135, 90, CW-225], [
                       (f'{number(case["T_max_C"])} °C máx.', f'{number(case["t_T_h"])} h',
                        'Núcleo de la vertida 4. Quedó a 20,36 °C del límite.'),
                       (f'{number(case["delta_C"], 3)} °C de Δ', f'{number(case["t_delta_h"])} h',
                        '48,27 °C en vertida 4 y 28,45 °C cerca de la cara x− de la vertida 1, al mismo tiempo.')],
                   height=37, size=9.8)
        self.note(L, 701, CW, 67, 'Cómo leer el pico diferencial',
                  'La separación vertical entre las curvas de arriba en cada instante produce la curva de abajo. El máximo ocurre mientras las caras expuestas y el suelo siguen intercambiando calor.', size=10)
        self.footer(8, 'Fuente  /  JSON de confirmación EPS 200 mm, SS/ERA5 2025')

    def profile_plot(self, top, bottom, marks, days, curves, limit, peak_day, peak_value):
        x0, x1 = L+40, W-L-17
        top_scale = marks[-1] + 2
        for mark in marks:
            y = bottom - mark * (bottom-top)/top_scale
            self.line(x0, y, x1, y, '#E2EAE3')
            self.text(mark, x0-8, y-5, 8, color=MUTED, align='right')
        for day in range(0, 29, 4):
            x = x0 + day*(x1-x0)/28
            self.line(x, top, x, bottom, '#E2EAE3')
            self.text(day, x, bottom+5, 8, color=MUTED, align='center')
        for values, color, dash in curves:
            path = self.c.beginPath()
            for i, (day, value) in enumerate(zip(days, values)):
                x = x0 + day*(x1-x0)/days[-1]
                y = H-bottom + value*(bottom-top)/top_scale
                if i:
                    path.lineTo(x, y)
                else:
                    path.moveTo(x, y)
            self.c.setStrokeColor(color)
            self.c.setLineWidth(1.25)
            self.c.setDash(dash)
            self.c.drawPath(path)
        y_limit = bottom-limit*(bottom-top)/top_scale
        self.line(x0, y_limit, x1, y_limit, RED, .8, (4, 3))
        self.text(f'Límite {limit} °C', x1-1, y_limit-12, 8.5, 'Bold', RED, 'right')
        xp = x0+peak_day*(x1-x0)/days[-1]
        yp = bottom-peak_value*(bottom-top)/top_scale
        self.line(xp, yp, xp, bottom, '#A28A55', .75, (3, 3))
        self.dot(xp, yp, 3.6, AMBER)

    def verification(self, counts):
        self.header(9, 'Pruebas', 'Qué comprobamos',
                    'Las pruebas analíticas evalúan el solver. Las corridas de defensa comprueban las métricas para esta geometría, estos insumos y la resolución ensayada.')
        self.subhead('Pruebas con solución conocida · dossier E06', 151)
        self.table(181, ['Prueba', 'Resultado observado', 'Qué comprueba'], [146, 162, CW-308], [
            ('Difusión sinusoidal 1D', 'Orden espacial ≈ 2; temporal ≈ 1', 'Discretización y Euler explícito.'),
            ('Fuente uniforme 3D', 'Error 1,34 × 10⁻¹² °C', 'Unidades e integración de Q.'),
            ('Caja adiabática 3D', 'Deriva relativa 1,51 × 10⁻¹⁶', 'Conservación sin flujos externos.'),
            ('Pared convectiva (Robin)', 'Error máximo 0,006081 °C', 'Flujo de borde frente a solución analítica.')], height=29, size=9.8)
        self.note(L, 343, CW, 96, 'Referencia de vertida única sin aislación',
                  'SS/ERA5 2025: el diferencial fue <b>43,673 → 44,191 → 44,940 °C</b> al pasar de barrido a cribado y a fino. Reducir paso o intervalo de registro cambió el resultado menos de 0,007 °C respecto al cribado. La clasificación siguió siendo desfavorable.')

        self.subhead('Control de la evidencia archivada', 464)
        cards = [(str(counts[0]), 'Corridas base', '60 de la matriz principal'),
                 (str(counts[1]), 'Corridas extendidas', 'Confirmación incluida'),
                 (str(counts[2]), 'Corridas piloto', 'Búsqueda de control')]
        for i, (value, label, sub) in enumerate(cards):
            width = (CW-20)/3
            x = L+i*(width+10)
            self.rect(x, 494, width, 77, MINT, radius=5)
            self.text(value, x+11, 500, 26, 'Title', TEAL)
            self.text(label, x+11, 534, 10, 'Bold')
            self.text(sub, x+11, 550, 8.7, color=MUTED)
        self.p(f'<b>{sum(counts)} corridas:</b> ZIP íntegros, indicadores y balances comprobados. En la extensión, residuo relativo máximo <b>9,04 × 10⁻¹⁶</b>. El recálculo de <b>36 filas agregadas</b> coincidió con sus CSV (diferencia menor que 10⁻¹²).',
               L, 591, CW, 10.7)
        self.p('<b>Reproducción offline:</b> se restauraron los paquetes y se regeneraron las tablas de 60 casos base y 6 casos finos, con cero pendientes de cálculo. <b>Pruebas del repositorio:</b> 265 del proyecto y 5 de la CLI raíz aprobadas en el repaso del 17-nov.',
               L, 647, CW, 10.7)
        self.p('Queda sin validar la respuesta de la fundación con sensores independientes en terreno. El balance comprueba la conservación numérica.',
               L, 718, CW, 10.2, MUTED)
        self.footer(9, 'Fuentes  /  E06, verificación de referencia y registro de progreso del 17-nov')

    def controls(self):
        self.header(10, 'Obra y preguntas', 'Controles y contingencias',
                    'El escenario de control combina preenfriamiento y aislación. El programa de monitoreo ayuda a revisar la respuesta durante colocación y enfriamiento.')
        half = (CW-12)/2
        self.note(L, 157, half, 161, 'Preenfriar a 12 °C',
                  'Confirmar suministro a <b>40 m³/h desde las 04:00</b>. Bajar 6 K requiere <b>8,894 GJ</b> de extracción ideal (155,2 kW térmicos en promedio). Dimensionamiento del equipo y pérdidas quedan por evaluar. Si se atrasa la primera colocación, sumar el atraso a D.', size=10.4)
        self.note(L+half+12, 157, half, 161, 'Aislar con EPS de 20 cm',
                  'EPS = poliestireno expandido. El modelo cubre caras de arriba y laterales desde la colocación y durante el horizonte, incluso tras el desmolde a 72 h en la configuración. La base conserva contacto con suelo. Confirmar disponibilidad, instalación y retiro.', bg=WHITE, size=10.4)

        self.subhead('Qué observar y cómo reaccionar', 341)
        self.table(374, ['Qué medir', 'Punto o momento', 'Ante un desvío'], [116, 189, CW-305], [
            ('Temperatura del núcleo', 'Zona caliente prevista, con redundancia.', 'Comprobar sensor y trayectoria.'),
            ('Cerca de la superficie', '~25 mm, cara crítica de la primera vertida, lado x− cerca del suelo.', 'Comparar a la vez máxima y diferencial.'),
            ('Ambiente y protecciones', 'Desde la colocación; registrar instalación, clima y desmolde.', 'Revisar el efecto antes de retirar EPS.')], height=50, size=10)
        self.p('Registrar al menos durante 14 días y extender si hay picos tardíos. En F01, acordar frecuencia, responsables y disparadores con márgenes que consideren la precisión de sensores y modelo.',
               L, 563, CW, 10.6, MUTED)
        self.note(L, 626, CW, 114, 'Tres preguntas para ensayar',
                  '<b>¿Por qué 15,92 h?</b> Es V/40 con una línea continua. <b>¿Qué mostró el 0%?</b> Ninguna de seis filas ponderadas de malla fina excedió los límites. <b>¿Qué puede cambiar la decisión?</b> El margen de malla, la capacidad real, la temperatura de suministro y el comportamiento del EPS en obra.', bg=CREAM, accent=AMBER)
        self.footer(10, 'Fuentes  /  guion, extensión y plan docente de control')

    def deliveries(self):
        self.header(11, 'Calendario y rúbrica', 'Qué llevar y qué entregar',
                    'Entregar el respaldo al inicio de la defensa y mantener el SHA para el artículo final, que se entrega por separado.')
        self.note(L, 154, CW, 118, 'Miércoles 18 · E13, taller de cierre · 5 puntos',
                  'Llevar repositorio ejecutable y SHA, IFC/voxelización, corrida completa de vertida única, ocho curvas originales, archivos de clima y verificación inicial. Llevar hasta tres preguntas. Priorizar recursos de obra, comparabilidad de SS/22A y fundamento para Arrhenius.')
        self.note(L, 286, CW, 141, 'Jueves 19 · Defensa · 40 puntos',
                  'Entregar al inicio PDF con autores, grupo y respaldo; enlace y SHA; entorno y comandos; curvas, sitio, inicio, zona y snapshot; configuraciones, escenarios, pesos y métricas por escenario y agregadas. Confirmar apertura offline en el equipo que se llevará.<br/><br/><b>Ensayo pendiente:</b> 7 min de exposición, 5 de preguntas y 1 de transición. Medir al cierre de las diapositivas 3, 6 y 9. Son 31 puntos grupales y 9 individuales. Todos deben poder explicar su trabajo.', bg=WHITE, size=10.2)
        self.note(L, 442, CW, 182, 'F01 · Artículo académico final · 20 puntos',
                  'Confirmar <b>fecha y hora en Canvas</b>. La pauta F01 dice viernes 20 y E13 anuncia traslado al lunes 23. Coordinar aprobación del <b>Centro de Escritura</b> antes del cierre del semestre. El registro consultado solo contiene el PDF de la defensa.<br/><br/>Entregar PDF en español con título, autores, grupo, curso y fecha, además del repositorio y SHA final, configuraciones, resultados y datos o acceso preciso. Guía de extensión: 4.000–6.000 palabras, resumen de 150–250, 4–6 palabras clave, figuras numeradas con unidades, referencias y anexo reproducible. Conservar el SHA de defensa y explicar las correcciones y su efecto.', bg=CREAM, accent=AMBER, size=10.2)
        self.subhead('Orden del artículo', 650)
        self.p('Introducción → caso e insumos → modelo continuo → discretización y verificación → incertidumbre y búsqueda → resultados → discusión y plan de control → conclusiones → referencias y reproducción.',
               L, 682, CW, 11)
        self.footer(11, 'Fuentes  /  pauta de defensa §7–8, guía E13 y pauta F01')

    def reproduce(self):
        self.header(12, 'Trazabilidad', 'Reproducir sin recalcular',
                    'Desde la raíz del repositorio y con el entorno de Python del proyecto instalado. Extraer cada ZIP en un destino vacío y conservar las corridas que ya estén archivadas.')
        self.subhead('Restaurar la campaña base', 150)
        self.code(177, [
            '$py = "proyecto/.venv/Scripts/python.exe"',
            'Expand-Archive proyecto/docs/evidencia_defensa/corridas.zip `',
            '  -DestinationPath proyecto/results/defensa',
            '& $py proyecto/scripts/defensa.py --nivel barrido --plan unica `',
            '  --curva M1_SS --clima era5_2025',
            '& $py proyecto/scripts/defensa.py --nivel barrido --procesos 3',
            '& $py proyecto/scripts/evidencia_defensa.py --nivel barrido',
        ])
        self.text('Esperado: 60 filas seleccionadas para el barrido, 0 por ejecutar.', L, 298, 9.8, color=MUTED)

        self.subhead('Restaurar la malla fina de EPS 200 mm', 329)
        self.code(357, [
            'Expand-Archive proyecto/docs/evidencia_extension_defensa/corridas.zip `',
            '  -DestinationPath proyecto/results/defensa_extension_larga',
            '& $py proyecto/scripts/explorar_defensa.py `',
            '  --estudio proyecto/configs/defensa_extension_clima.yaml `',
            '  --salida proyecto/results/defensa_extension_larga --plan eps200_T12 `',
            '  --nivel fino --horizonte-extendido 672 --procesos 1',
        ])
        self.text('Esperado: 6 seleccionadas, 0 pendientes.', L, 464, 9.8, color=MUTED)

        self.subhead('Fuentes versionadas', 501)
        commitments = [
            ('Paquete de defensa revisado', DEFENSE),
            ('Código e insumos de la campaña base', 'fc95932a4fd3d08652679052c342b63e71858b9c'),
            ('Corridas finales de la extensión', 'aede6bfb38b4e69c92511c598fa62fecdfd6e427'),
        ]
        for i, (label, sha) in enumerate(commitments):
            y = 531 + i * 21
            self.text(label, L, y, 10)
            self.link(sha, f'{REPO}/commit/{sha}', L+200, y, 8.7)
        links = [('Guía técnica base', 'proyecto/docs/defensa.md'),
                 ('Extensión y salvedad de malla', 'proyecto/docs/extension_defensa.md'),
                 ('Resultados por escenario', 'proyecto/docs/evidencia_extension_defensa/escenarios.csv'),
                 ('Registro de progreso', 'progreso.md'),
                 ('PDF para exponer', 'Defensa%20final/Defensa%20final%20-%20Grupo%201.pdf'),
                 ('Guion del grupo', 'Archivos%20Extra/Defensa%20final/guion.md')]
        for i, (label, path) in enumerate(links):
            self.link(label, snapshot(path), L+(i%2)*261, 609+(i//2)*23)
        self.p('Documentos del curso consultados por separado: «Pregunta que deben responder» (defensa), «E13 - Miércoles: taller de consultas y cierre técnico» y «F01 - Artículo académico final».',
               L, 704, CW, 10, MUTED)
        self.footer(12, 'P02-MCOC  /  Grupo 1')

    def code(self, y, lines):
        self.rect(L, y, CW, 17 + len(lines)*12.9, DARK, radius=5)
        for i, value in enumerate(lines):
            assert pdfmetrics.stringWidth(value, 'Mono', 8.4) < CW - 22, value
            self.text(value, L+11, y+8+i*12.9, 8.4, 'Mono', '#EEF1E7')


def main():
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    stages = [r for r in csv_rows(BASE / 'cronogramas.csv') if r['plan'] == 'unica']
    base = {(r['plan'], r['pesos']): r for r in csv_rows(BASE / 'comparacion.csv') if r['nivel'] == 'barrido'}
    candidate = [r for r in csv_rows(EXT / 'escenarios.csv') if r['plan'] == 'eps200_T12']
    fine = sorted((r for r in candidate if r['nivel'] == 'fino'), key=lambda r: (r['curva'] != 'M1_SS', r['clima']))
    confirmation, = (r for r in candidate if r['nivel'] == 'confirmacion')
    source = PROJECT / 'data/hidratacion/source_terms.txt'
    hydration = [tuple(map(float, line.split())) for line in source.read_text(encoding='utf-8').splitlines()
                 if line.strip() and not line.startswith('#')]
    counts = []
    for evidence in (BASE, EXT, PILOTS):
        with ZipFile(evidence / 'corridas.zip') as archive:
            counts.append(sum(Path(name).suffix == '.json' for name in archive.namelist()))
    with ZipFile(EXT / 'corridas.zip') as archive:
        name, = (n for n in archive.namelist() if 'confirmacion__eps200_T12__M1_SS__era5_2025' in n)
        critical = loads(archive.read(name))
    assert len(stages) == 5 and len(base) == 20 and len(fine) == 6
    assert all(r['I_F'] == '0' for r in fine) and counts == [79, 35, 14]
    assert len(hydration[0]) == 9 and all(len(row) == 9 for row in hydration)
    guide = Guide()
    guide.cover()
    guide.schedule(stages)
    guide.inputs(hydration)
    guide.physics()
    guide.scenarios(fine)
    guide.comparison(base)
    guide.sensitivity(confirmation)
    guide.profiles(critical)
    guide.verification(counts)
    guide.controls()
    guide.deliveries()
    guide.reproduce()
    guide.c.save()
    print(OUTPUT)


if __name__ == '__main__':
    main()
