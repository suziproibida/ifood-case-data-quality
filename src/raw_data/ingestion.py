import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import boto3
import requests
import yaml
from awsglue.utils import getResolvedOptions


_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _is_s3_path(path: str) -> bool:
    return isinstance(path, str) and path.startswith("s3://")


def parse_s3_path(s3_path: str) -> tuple[str, str]:
    parsed = urlparse(s3_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    if parsed.scheme != "s3" or not bucket or not key:
        raise ValueError(f"Caminho S3 inválido: {s3_path}")

    return bucket, key


def read_config() -> dict:
    args = getResolvedOptions(sys.argv, ["config_s3_uri"])
    config_s3_uri = args["config_s3_uri"]

    bucket, key = parse_s3_path(config_s3_uri)

    response = _get_s3_client().get_object(Bucket=bucket, Key=key)
    config_content = response["Body"].read().decode("utf-8")
    config = yaml.safe_load(config_content)

    if not isinstance(config, dict):
        raise ValueError("O arquivo YAML deve conter um objeto na raiz.")

    required_sections = ["paths", "nyc_taxi", "download"]
    missing_sections = [
        section for section in required_sections if section not in config
    ]

    if missing_sections:
        raise ValueError(
            f"Seções ausentes no YAML: {', '.join(missing_sections)}"
        )

    return config


config = read_config()

BASE_URL = config["nyc_taxi"]["base_url"].rstrip("/")
YEAR = int(config["nyc_taxi"]["year"])
SERVICE_TYPES = config["nyc_taxi"]["service_types"]

RAW_DATA_PATH = config["paths"]["raw_data"].rstrip("/") + "/"

CHUNK_SIZE = int(config["download"]["chunk_size_mb"]) * 1024 * 1024
TIMEOUT = int(config["download"]["timeout_seconds"])


def get_last_month_to_download(year: int) -> int:
    today = datetime.today()

    if year < today.year:
        return 13

    if year == today.year:
        # Baixa apenas meses já concluídos.
        return today.month

    raise ValueError("O ano informado está no futuro.")


def s3_object_exists(path: str) -> bool:
    if not _is_s3_path(path):
        return Path(path).exists()

    bucket, key = parse_s3_path(path)

    try:
        _get_s3_client().head_object(Bucket=bucket, Key=key)
        return True
    except _get_s3_client().exceptions.ClientError as error:
        status_code = error.response["ResponseMetadata"]["HTTPStatusCode"]

        if status_code == 404:
            return False

        raise


def upload_to_s3(content: bytes, output_path: str) -> None:
    if not _is_s3_path(output_path):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return

    bucket, key = parse_s3_path(output_path)
    _get_s3_client().put_object(Bucket=bucket, Key=key, Body=content)


def download_file(url: str, output_path: str) -> bool:
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as response:
            if response.status_code in [403, 404]:
                print(f"Arquivo indisponível ({response.status_code}): {url}")
                return False

            response.raise_for_status()

            if not _is_s3_path(output_path):
                path = Path(output_path)
                path.parent.mkdir(parents=True, exist_ok=True)

                with path.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            file.write(chunk)

                print(f"Download concluído: {output_path}")
                return True

            content = b"".join(
                chunk
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE)
                if chunk
            )
            upload_to_s3(content=content, output_path=output_path)

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
                f"{RAW_DATA_PATH}"
                f"{service_type}/"
                f"year={YEAR}/"
                f"month={month_str}/"
                f"{file_name}"
            )

            if s3_object_exists(output_path):
                print(f"Arquivo já existe, ignorando: {output_path}")
                continue

            if not download_file(url, output_path):
                print(f"Parando frota {service_type} e indo para a próxima.")
                break

        print(f"Finalizado download da frota: {service_type}")


if __name__ == "__main__":
    main()
