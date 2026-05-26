import logging
import sys
from datetime import date
from urllib.parse import urlparse

import boto3
import requests
import yaml
from awsglue.utils import getResolvedOptions  # type: ignore
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

s3 = boto3.client("s3")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)

    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"URI S3 inválida: {uri}")

    return parsed.netloc, parsed.path.lstrip("/")


def load_config(config_uri: str) -> dict:
    bucket, key = parse_s3_uri(config_uri)

    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")

    config = yaml.safe_load(content)

    if not isinstance(config, dict):
        raise ValueError("O arquivo de configuração YAML está vazio ou inválido.")

    return config


def get_last_available_month(year: int) -> int:
    today = date.today()

    if year > today.year:
        raise ValueError(f"O ano {year} está no futuro.")

    if year < today.year:
        return 12

    return today.month - 1


def build_output_key(
    base_prefix: str,
    service_type: str,
    year: int,
    month: int,
    file_name: str,
) -> str:
    parts = [
        base_prefix.rstrip("/"),
        f"{service_type}_taxi",
        f"year={year}",
        f"month={month:02d}",
        file_name,
    ]
    return "/".join(part for part in parts if part)


def object_exists(bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False

        raise


def download_to_s3(
    session: requests.Session,
    url: str,
    destination_bucket: str,
    destination_key: str,
    timeout: int,
    transfer_config: TransferConfig,
) -> bool:
    try:
        with session.get(url, stream=True, timeout=(10, timeout)) as response:
            if response.status_code in {403, 404}:
                LOGGER.warning(
                    "Arquivo indisponível (%s): %s",
                    response.status_code,
                    url,
                )
                return False

            response.raise_for_status()
            response.raw.decode_content = True

            s3.upload_fileobj(
                response.raw,
                destination_bucket,
                destination_key,
                Config=transfer_config,
                ExtraArgs={"ContentType": "application/octet-stream"},
            )

        LOGGER.info("Download concluído: s3://%s/%s", destination_bucket, 
                    destination_key)
        return True

    except requests.exceptions.RequestException as error:
        LOGGER.error("Erro ao baixar %s: %s", url, error)
        return False

    except ClientError as error:
        LOGGER.error(
            "Erro ao gravar s3://%s/%s: %s",
            destination_bucket,
            destination_key,
            error,
        )
        raise


def main() -> None:
    args = getResolvedOptions(sys.argv, ["config_path"])
    config = load_config(args["config_path"])

    taxi_config = config["nyc_taxi"]
    download_config = config["download"]

    base_url = taxi_config["base_url"].rstrip("/")
    year = int(taxi_config["year"])
    service_types = taxi_config["service_types"]

    chunk_size = int(download_config["chunk_size_mb"]) * 1024 * 1024
    timeout = int(download_config["timeout_seconds"])

    destination_bucket, destination_prefix = parse_s3_uri(
        config["paths"]["raw_data"]
    )

    transfer_config = TransferConfig(
        multipart_threshold=chunk_size,
        multipart_chunksize=chunk_size,
    )

    last_month = get_last_available_month(year)

    if last_month == 0:
        LOGGER.info("Ainda não existem meses completos disponíveis para %s.", year)
        return

    with requests.Session() as session:
        for service_type in service_types:
            LOGGER.info("Iniciando download da frota: %s", service_type)

            for month in range(1, last_month + 1):
                file_name = f"{service_type}_tripdata_{year}-{month:02d}.parquet"
                url = f"{base_url}/{file_name}"

                destination_key = build_output_key(
                    destination_prefix,
                    service_type,
                    year,
                    month,
                    file_name,
                )

                if object_exists(destination_bucket, destination_key):
                    LOGGER.info(
                        "Arquivo já existe, ignorando: s3://%s/%s",
                        destination_bucket,
                        destination_key,
                    )
                    continue

                downloaded = download_to_s3(
                    session=session,
                    url=url,
                    destination_bucket=destination_bucket,
                    destination_key=destination_key,
                    timeout=timeout,
                    transfer_config=transfer_config,
                )

                if not downloaded:
                    LOGGER.info(
                        "Interrompendo downloads da frota %s após arquivo ausente.",
                        service_type,
                    )
                    break

            LOGGER.info("Download finalizado para a frota: %s", service_type)


if __name__ == "__main__":
    main()
