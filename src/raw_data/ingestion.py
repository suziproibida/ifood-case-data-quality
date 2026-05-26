from datetime import datetime
from urllib.parse import urlparse
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


# Lazy-loaded S3 client: import boto3 only when needed
_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        try:
            import boto3
        except Exception:
            _s3_client = None
            return None
        _s3_client = boto3.client("s3")
    return _s3_client


def get_last_month_to_download(year: int) -> int:
    today = datetime.today()

    if year < today.year:
        return 13

    if year == today.year:
        return today.month

    raise ValueError("O ano informado está no futuro.")


def _is_s3_path(path) -> bool:
    return isinstance(path, str) and path.startswith("s3://")


def parse_s3_path(s3_path: str) -> tuple[str, str]:
    parsed = urlparse(s3_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def s3_object_exists(path) -> bool:
    if not _is_s3_path(path):
        return Path(path).exists()

    client = _get_s3_client()
    if client is None:
        return False

    bucket, key = parse_s3_path(path)
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def upload_to_s3(content: bytes, output_path) -> None:
    if not _is_s3_path(output_path):
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return

    client = _get_s3_client()
    if client is None:
        raise RuntimeError("boto3 is required to upload to s3:// paths")

    bucket, key = parse_s3_path(output_path)
    client.put_object(Bucket=bucket, Key=key, Body=content)


def download_file(url: str, output_path) -> bool:
    try:
        response = requests.get(url, stream=True, timeout=TIMEOUT)

        if response.status_code in [403, 404]:
            print(f"Arquivo indisponível ({response.status_code}): {url}")
            return False

        response.raise_for_status()

        if not _is_s3_path(output_path):
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)

            with p.open("wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)

            print(f"Download concluído: {output_path}")
            return True

        # s3:// path: collect bytes and upload
        content = b"".join(response.iter_content(chunk_size=CHUNK_SIZE))
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

            found = download_file(url, output_path)

            if not found:
                print(f"Parando frota {service_type} e indo para a próxima.")
                break

        print(f"Finalizado download da frota: {service_type}")


if __name__ == "__main__":
    main()
