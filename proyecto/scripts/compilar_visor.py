"""Incluye la biblioteca de gráficos en el HTML para mantener el visor autocontenido.

python proyecto/scripts/compilar_visor.py
python proyecto/scripts/compilar_visor.py --check
"""
import argparse
from pathlib import Path

INICIO='// BEGIN ANALISIS_TERMICO_GENERADO\n'
FIN='// END ANALISIS_TERMICO_GENERADO\n'


def compilar(raiz):
    archivo=raiz/'visor_e08/index.html'
    html=archivo.read_text(encoding='utf-8')
    biblioteca=(raiz/'visor_e08/analisis.js').read_text(encoding='utf-8').rstrip()+'\n'
    bloque=INICIO+biblioteca+FIN
    if INICIO in html:
        antes,resto=html.split(INICIO,1)
        _,despues=resto.split(FIN,1)
        nuevo=antes+bloque+despues
    else:
        externo='<script src="/analisis.js"></script>\n'
        if externo not in html:
            raise ValueError('No se encontró la ruta de inclusión de analisis.js.')
        nuevo=html.replace(externo,'',1)
        inicio_script="<script>\n'use strict';\n"
        if inicio_script not in nuevo:
            raise ValueError('No se encontró el script principal del visor.')
        nuevo=nuevo.replace(inicio_script,inicio_script+bloque,1)
    return archivo,html,nuevo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    archivo,anterior,nuevo=compilar(Path(__file__).resolve().parents[1])
    if args.check:
        if anterior!=nuevo:
            parser.exit(1,'La biblioteca del visor está desactualizada: ejecutar compilar_visor.py.\n')
        print('Biblioteca del visor sincronizada.')
    else:
        archivo.write_text(nuevo,encoding='utf-8')
        print('Visor autocontenido actualizado.')


if __name__=='__main__':
    main()
