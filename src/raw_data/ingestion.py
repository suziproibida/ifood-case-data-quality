from datetime import datetime
from pathlib import Path
import requests

from config.read_config import read_config


config = read_config()

BASE_URL = config["nyc_taxi"]["base_url"]
YEAR = config["nyc_taxi"]["year"]
SERVICE_TYPES = config["nyc_taxi"]["service_types"]

RAW_DATA_PATH = config["paths"]["raw_data"]

CHUNK_SIZE = config["download"]["chunk_size_mb"] * 1024 * 1024
TIMEOUT = config["download"]["timeout_seconds"]


def get_last_month_to_download(year: int) -> int:
    today = datetime.today()

    if year < today.year:
        return 13

    if year == today.year:
        return today.month

    raise ValueError("O ano informado está no futuro.")


def download_file(url: str, output_path: Path) -> bool:
    try:
        response = requests.get(url, stream=True, timeout=TIMEOUT)

        if response.status_code in [403, 404]:
            print(f"Arquivo indisponível ({response.status_code}): {url}")
            return False

        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    file.write(chunk)

        print(f"Download concluído: {output_path}")
        return True

    except requests.exceptions.RequestException as error:
        print(f"Erro ao baixar {url}: {error}")
        return False


def main() -> None:
    last_month = get_last_month_to_download(YEAR)

    for service_type in SERVICE_TYPES:
        print(f"\nIniciando download da frota: {service_type}")

        for month in range(1, last_month):
            month_str = f"{month:02d}"

            file_name = f"{service_type}_tripdata_{YEAR}-{month_str}.parquet"
            url = f"{BASE_URL}/{file_name}"

            output_path = (
                Path("data/landing")
                / f"{service_type}_taxi"
                / f"year={YEAR}"
                / f"month={month_str}"
                / file_name
            )

            if output_path.exists():
                print(f"Arquivo já existe, ignorando: {output_path}")
                continue

            found = download_file(url, output_path)

            if not found:
                print(f"Parando frota {service_type} e indo para a próxima.")
                break

        print(f"Finalizado download da frota: {service_type}")


if __name__ == "__main__":
    main()