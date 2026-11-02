"""Abre E08 con doble clic; reutiliza un servidor o lo inicia sin consola."""
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser

RAIZ = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8765'


def disponible():
    # El servicio es local: no enviar su consulta a un proxy de Internet.
    try:
        with build_opener(ProxyHandler({})).open(URL+'/api/plan', timeout=.6) as respuesta:
            plan = json.load(respuesta)
        return isinstance(plan, dict) and {'ifc', 'material', 'vertidas', 'paso_m'} <= plan.keys()
    except (URLError, OSError, ValueError, TypeError):
        return False


def iniciar():
    if disponible():
        return
    carpeta = RAIZ/'results/e08'
    carpeta.mkdir(parents=True, exist_ok=True)
    registro = carpeta/'servidor.log'
    python = Path(sys.executable).with_name('python.exe')
    with registro.open('a', encoding='utf-8') as log:
        proceso = subprocess.Popen([str(python), '-u', str(RAIZ/'scripts/demo_e08.py')],
                                   cwd=RAIZ.parent, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    limite = time.monotonic()+30
    while time.monotonic() < limite:
        if disponible():
            return
        if proceso.poll() is not None:
            # Si hubo dos dobles clics simultáneos, el otro proceso puede
            # haber ocupado el puerto e iniciado el servidor correctamente.
            if disponible():
                return
            raise RuntimeError(f'No se pudo iniciar el visualizador. Detalle en:\n{registro}')
        time.sleep(.25)
    raise RuntimeError(f'El visualizador no respondió en 30 segundos. Detalle en:\n{registro}')


def main():
    try:
        iniciar()
        if '--sin-abrir' not in sys.argv:
            webbrowser.open(URL)
        elif sys.stdout is not None:
            print(URL)
        return 0
    except Exception as exc:
        if '--sin-abrir' in sys.argv:
            raise
        from tkinter import Tk, messagebox
        ventana = Tk()
        ventana.withdraw()
        messagebox.showerror('Visualizador E08', str(exc), parent=ventana)
        ventana.destroy()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
