"""Pruebas de humo de la CLI de mcplan (etapa E00)."""

from pathlib import Path

import pytest

from mcplan.cli import main
from mcplan.config import ErrorConfiguracion, cargar_sitio

RAIZ = Path(__file__).resolve().parents[1]
SITIO = RAIZ / "configs" / "site.yaml"


def test_site_oficial_existe():
    assert SITIO.is_file(), f"Falta la configuración oficial: {SITIO}"


def test_cargar_sitio_datos_oficiales():
    sitio = cargar_sitio(SITIO)
    assert sitio.grupo == "G1"
    assert sitio.etapa_actual == "E00"
    assert sitio.parque_eolico == "Parque Eólico Wayra"
    assert sitio.localidad == "Taltal / Zona de Reserva Eólica"
    assert sitio.region == "Antofagasta"
    assert sitio.latitud == pytest.approx(-24.952830)
    assert sitio.longitud == pytest.approx(-70.004838)
    assert sitio.zona_horaria == "America/Santiago"


def test_cli_info_muestra_datos(capsys):
    codigo = main(["info", "--site", str(SITIO)])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "G1" in salida
    assert "E00" in salida
    assert "Parque Eólico Wayra" in salida
    assert "Taltal / Zona de Reserva Eólica" in salida
    assert "Antofagasta" in salida
    assert "-24.952830" in salida
    assert "-70.004838" in salida
    assert "America/Santiago" in salida


def test_cli_site_inexistente_error_claro(capsys, tmp_path):
    faltante = tmp_path / "no_existe.yaml"
    codigo = main(["info", "--site", str(faltante)])
    err = capsys.readouterr().err
    assert codigo == 2
    assert "Error" in err
    assert "no_existe.yaml" in err


def test_cargar_sitio_inexistente_lanza():
    with pytest.raises(ErrorConfiguracion):
        cargar_sitio(Path("ruta") / "inexistente.yaml")
