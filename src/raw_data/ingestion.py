from datetime import datetime
from urllib.parse import urlparse

import boto3
import requests

from config.read_config import read_config


config = read_config()

BASE_URL = config["nyc_taxi"]["base_url"]
YEAR = config["nyc_taxi"]["year"]
SERVICE_TYPES = config["nyc_taxi"]["service_types"]

RAW_DATA_PATH = config["paths"]["raw_data"]

CHUNK_SIZE = config["download"]["chunk_size_mb"] * 1024 * 1024
TIMEOUT = config["download"]["timeout_seconds"]

s3_client = boto3.client("s3")


def get_last_month_to_download(year: int) -> int:
    today = datetime.today()

    if year < today.year:
        return 13

    if year == today.year:
        return today.month

    raise ValueError("O ano informado está no futuro.")


def parse_s3_path(s3_path: str) -> tuple[str, str]:
    parsed = urlparse(s3_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def s3_object_exists(s3_path: str) -> bool:
    bucket, key = parse_s3_path(s3_path)

    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def upload_to_s3(content: bytes, output_s3_path: str) -> None:
    bucket, key = parse_s3_path(output_s3_path)

    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
    )


def download_file(url: str, output_s3_path: str) -> bool:
    try:
        response = requests.get(url, stream=True, timeout=TIMEOUT)

        if response.status_code in [403, 404]:
            print(f"Arquivo indisponível ({response.status_code}): {url}")
            return False

        response.raise_for_status()

        upload_to_s3(
            content=response.content,
            output_s3_path=output_s3_path,
        )

        print(f"Download concluído: {output_s3_path}")
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

            output_s3_path = (
                f"{RAW_DATA_PATH}"
                f"{service_type}/"
                f"year={YEAR}/"
                f"month={month_str}/"
                f"{file_name}"
            )

            if s3_object_exists(output_s3_path):
                print(f"Arquivo já existe, ignorando: {output_s3_path}")
                continue

            found = download_file(url, output_s3_path)

            if not found:
                print(f"Parando frota {service_type} e indo para a próxima.")
                break

        print(f"Finalizado download da frota: {service_type}")


if __name__ == "__main__":
    main()