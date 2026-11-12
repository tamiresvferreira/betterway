import sys
from pathlib import Path

# Permite "import risco" a partir de src/estudo_b_risco_vida/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "estudo_b_risco_vida"))
