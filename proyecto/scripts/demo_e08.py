"""Demo E08: servidor local 3D o ejecución por lote del mismo pipeline.

python proyecto/scripts/demo_e08.py
python proyecto/scripts/demo_e08.py --ejecutar --plan proyecto/configs/e08.json
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import sys
import uuid
from urllib.parse import urlparse

from mcplan.pipeline import Pipeline, cargar_plan
from mcplan.version_demo import version_visualizador

RAIZ = Path(__file__).resolve().parents[1]


def crear_servidor(plan, puerto, salida, resultado_inicial=None):
    pipeline = Pipeline()
    executor = ThreadPoolExecutor(max_workers=1)
    candado = threading.Lock()
    estado = dict(estado='idle', mensaje='Listo para ejecutar', resultado=None,
                  carpeta=None, carpeta_resultado=None)
    if resultado_inicial is not None:
        estado.update(estado='done',mensaje='Resultado guardado recuperado; sin nueva simulación',
                      resultado=resultado_inicial,carpeta=resultado_inicial.get('carpeta_origen'),
                      carpeta_resultado=resultado_inicial.get('carpeta_origen'))
    salida = Path(salida).resolve()
    version = version_visualizador()

    def ejecutar(entrada, convergencia, destino):
        def progreso(mensaje):
            with candado:
                estado['mensaje'] = mensaje
        try:
            resultado = pipeline.ejecutar(entrada, destino, progreso, convergencia)
            with candado:
                estado.update(estado='done', mensaje='Simulación completada', resultado=resultado,
                              carpeta_resultado=str(destino))
        except Exception as exc:
            with candado:
                estado.update(estado='error', mensaje=f'{type(exc).__name__}: {exc}')

    class Handler(BaseHTTPRequestHandler):
        def responder(self, datos, codigo=200, tipo='application/json; charset=utf-8'):
            raw = datos if isinstance(datos, bytes) else json.dumps(datos, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            ruta = urlparse(self.path).path
            if ruta in ('/', '/index.html'):
                self.responder((RAIZ/'visor_e08/index.html').read_bytes(), tipo='text/html; charset=utf-8')
            elif ruta == '/analisis.js':
                self.responder((RAIZ/'visor_e08/analisis.js').read_bytes(), tipo='text/javascript; charset=utf-8')
            elif ruta == '/api/plan':
                self.responder(plan)
            elif ruta == '/api/version':
                self.responder(dict(aplicacion='mcplan-e08',version=version))
            elif ruta == '/api/estado':
                with candado:
                    resumen = {k: v for k, v in estado.items() if k != 'resultado'}
                self.responder(resumen)
            elif ruta == '/api/resultado':
                with candado:
                    resultado = estado['resultado']
                self.responder(resultado if resultado is not None else {'error': 'Todavía no hay resultados'}, 200 if resultado is not None else 404)
            else:
                self.responder({'error': 'Ruta inexistente'}, 404)

        def do_POST(self):
            if self.path not in ('/api/ejecutar','/api/cerrar'):
                self.responder({'error': 'Ruta inexistente'}, 404)
                return
            origen = self.headers.get('Origin')
            permitidos = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if origen is not None and origen not in permitidos:
                self.responder({'error': 'Origen no permitido'}, 403)
                return
            if self.path == '/api/cerrar':
                with candado:
                    ocupado = estado['estado']=='running'
                if ocupado:
                    self.responder({'error':'Hay una simulación en curso; espera a que termine.'},409)
                    return
                self.responder({'estado':'cerrando'})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            try:
                longitud = int(self.headers.get('Content-Length', '0'))
                if longitud <= 0 or longitud > 65536:
                    raise ValueError('Entrada JSON vacía o demasiado grande.')
                entrada = json.loads(self.rfile.read(longitud))
                if set(entrada) != {'plan', 'convergencia'} or type(entrada['convergencia']) is not bool:
                    raise ValueError('Se requieren plan y convergencia booleana.')
                # Los archivos del caso se eligen al iniciar el servidor/CLI;
                # la interfaz modifica parámetros, no las rutas del proceso.
                entrada['plan']['ifc'] = plan['ifc']
                entrada['plan']['material'] = plan['material']
                if 'opciones' in plan:  # catálogos y carpeta de snapshots: los fija el servidor
                    entrada['plan']['opciones'] = plan['opciones']
                with candado:
                    if estado['estado'] == 'running':
                        self.responder({'error': 'Ya hay una simulación en ejecución'}, 409)
                        return
                    destino = salida/uuid.uuid4().hex[:12]
                    estado.update(estado='running', mensaje='Preparando pipeline', carpeta=str(destino))
                executor.submit(ejecutar, entrada['plan'], entrada['convergencia'], destino)
                self.responder({'estado': 'running'}, 202)
            except (ValueError, TypeError, KeyError) as exc:
                self.responder({'error': str(exc)}, 400)

        def log_message(self, *_):
            pass

    servidor = ThreadingHTTPServer(('127.0.0.1', puerto), Handler)
    return servidor, executor


def recuperar_resultado(archivo, plan_base):
    from mcplan.indicadores import reconstruir_indicadores

    resultado = json.loads(archivo.read_text(encoding='utf-8-sig'))
    if not resultado['fotogramas']:
        raise ValueError('La corrida guardada no contiene fotogramas.')
    if not resultado.get('indicadores'):
        resultado['indicadores'] = reconstruir_indicadores(resultado)
    resultado['carpeta_origen'] = str(archivo.resolve().parent)
    plan = resultado['plan'].copy()
    plan['opciones'] = dict(plan_base.get('opciones', {}), restaurado=True)
    return plan, resultado


def main():
    # La consola/redirect de Windows puede usar cp1252; el progreso incluye Δx.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--plan', type=Path, default=RAIZ/'configs/e08_demo.yaml')
    parser.add_argument('--puerto', type=int, default=8765)
    parser.add_argument('--salida', type=Path, default=RAIZ/'results/e08')
    parser.add_argument('--ejecutar', action='store_true', help='Ejecutar por lote sin servidor; incluye convergencia.')
    parser.add_argument('--resultado',type=Path,help='Abrir una corrida guardada y reconstruir sus indicadores sin simular.')
    parser.add_argument('--restaurar-ultimo', action='store_true', help='Recuperar la corrida completa más reciente.')
    args = parser.parse_args()
    plan = cargar_plan(args.plan)
    resultado_inicial = None
    if args.resultado:
        if args.ejecutar:
            parser.error('--resultado no se combina con --ejecutar.')
        plan, resultado_inicial = recuperar_resultado(args.resultado, plan)
    elif args.restaurar_ultimo and not args.ejecutar:
        archivos = sorted(args.salida.glob('*/resultado.json'),
                          key=lambda archivo: archivo.stat().st_mtime, reverse=True)
        for archivo in archivos:
            try:
                plan, resultado_inicial = recuperar_resultado(archivo, plan)
                break
            except (OSError, ValueError, KeyError, TypeError) as exc:
                print(f'No se pudo recuperar {archivo}: {exc}', file=sys.stderr)
    if args.ejecutar:
        destino = args.salida/'lote'
        resultado = Pipeline().ejecutar(plan, destino, print)
        print(f'Resultados: {destino.resolve()}')
        for fila in resultado['volumenes']:
            if fila['vertida_id'] == 'total':
                print(f'Δx={fila["paso_m"]:g} m: error total={fila["error_relativo"]:.3%}')
        return 0
    servidor, executor = crear_servidor(plan, args.puerto, args.salida,resultado_inicial)
    print(f'Demo E08: http://127.0.0.1:{servidor.server_port}', flush=True)
    print('Detener con Ctrl+C. Los cálculos se ejecutan en Python; el navegador muestra los resultados.', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        executor.shutdown(wait=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
