import sys
from pathlib import Path

import pandas as pd
import pytest

# Permite "import risco" a partir de src/estudo_b_risco_vida/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "estudo_b_risco_vida"))
# Permite "import visao" a partir de src/visao/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "visao"))
# Permite "import mensagens" etc. a partir de src/central/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "central"))


@pytest.fixture
def treino_sintetico():
    # 10 atropelamentos no mesmo ponto A (2 fatais) + 1 fatal isolado em B, longe.
    a = [{"latitude": -23.55, "longitude": -46.63, "fatal": i < 2, "tipo_via": "VIAS URBANAS"} for i in range(10)]
    b = [{"latitude": -23.70, "longitude": -46.70, "fatal": True, "tipo_via": "ESTRADAS E RODOVIAS"}]
    return pd.DataFrame(a + b)
