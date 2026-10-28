"""Verifica parámetros externos y rechazo de dt en la demostración en vivo."""
from pathlib import Path
import subprocess
import sys
import pytest

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/verification_nd.py'

@pytest.mark.parametrize('args',[
    ['--dim','3','--n','8','--longitudes','1','1.3','.8','--tiempo','1000','--k','2.5'],
    ['--caso','fuente','--dim','2','--fuente','1500','--tiempo','1000'],
    ['--caso','robin','--dim','1','--h','15','--ambiente','10','--tiempo','1000'],
])
def test_demostracion_parametrizada(args):
    r = subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True,text=True)
    assert r.returncode == 0,r.stderr
    assert 'Residuo balance=' in r.stdout


def test_demostracion_rechaza_dt_inestable():
    r = subprocess.run([sys.executable,str(SCRIPT),'--dim','3','--dt','1000000'],
                       capture_output=True,text=True)
    assert r.returncode == 2
    assert 'inestable' in r.stderr
