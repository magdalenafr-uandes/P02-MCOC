"""El panel y su módulo se sirven junto a una corrida recuperada, sin simular."""
import importlib.util
import json
from pathlib import Path
import threading
from urllib.request import urlopen


def test_servidor_publica_script_y_resultado_recuperado(tmp_path):
    ruta=Path(__file__).resolve().parents[1]/'scripts/demo_e08.py'
    spec=importlib.util.spec_from_file_location('demo_indicadores_http',ruta)
    modulo=importlib.util.module_from_spec(spec);spec.loader.exec_module(modulo)
    resultado={'indicadores':{'version':1},'carpeta_origen':'corrida_guardada'}
    servidor,executor=modulo.crear_servidor({},0,tmp_path,resultado)
    hilo=threading.Thread(target=servidor.serve_forever,daemon=True);hilo.start()
    url=f'http://127.0.0.1:{servidor.server_port}'
    try:
        with urlopen(url+'/analisis.js',timeout=3) as r:
            assert r.headers.get_content_type()=='text/javascript'
            assert b'AnalisisTermico' in r.read()
        with urlopen(url+'/api/estado',timeout=3) as r:
            estado=json.load(r)
            assert estado['estado']=='done' and 'sin nueva' in estado['mensaje']
        with urlopen(url+'/api/resultado',timeout=3) as r:
            assert json.load(r)==resultado
    finally:
        servidor.shutdown();servidor.server_close();executor.shutdown(wait=True);hilo.join(timeout=3)
