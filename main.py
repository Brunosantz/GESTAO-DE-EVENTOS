"""
Ponto de entrada da API.
Expõe também Base, engine, modelos e demais objetos do módulo original.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
api_path = BASE_DIR / "GESTAO DE EVENTOS.py"

spec = spec_from_file_location("gestao_eventos_module", api_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Não foi possível carregar o módulo de {api_path}")

module = module_from_spec(spec)
spec.loader.exec_module(module)

for nome, valor in vars(module).items():
    if not nome.startswith("_"):
        globals()[nome] = valor

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
