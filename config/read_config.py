from pathlib import Path
import yaml


def read_config(config_path: str = "config/config.yaml") -> dict:
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")

    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)