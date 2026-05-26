# import pytest
# import requests
# from src.raw_data import ingestion


# class FakeDatetime:
#     """Fake datetime class for deterministic tests."""

#     current_year = 2026
#     current_month = 5

#     @classmethod
#     def today(cls):
#         class Today:
#             year = cls.current_year
#             month = cls.current_month

#         return Today()


# class FakeResponse:
#     def __init__(self, status_code=200, chunks=None, should_raise=False):
#         self.status_code = status_code
#         self._chunks = chunks or [b"abc", b"", b"def"]
#         self.should_raise = should_raise

#     def raise_for_status(self):
#         if self.should_raise:
#             raise requests.exceptions.HTTPError("server error")

#     def iter_content(self, chunk_size):
#         return iter(self._chunks)


# def test_get_last_month_for_past_year(monkeypatch):
#     monkeypatch.setattr(ingestion, "datetime", FakeDatetime)
#     assert ingestion.get_last_month_to_download(2025) == 13


# def test_get_last_month_for_current_year(monkeypatch):
#     monkeypatch.setattr(ingestion, "datetime", FakeDatetime)
#     assert ingestion.get_last_month_to_download(2026) == 5


# def test_get_last_month_for_future_year(monkeypatch):
#     monkeypatch.setattr(ingestion, "datetime", FakeDatetime)

#     with pytest.raises(ValueError, match="ano informado está no futuro"):
#         ingestion.get_last_month_to_download(2027)


# @pytest.mark.parametrize("status_code", [403, 404])
# def test_download_file_returns_false_when_file_is_unavailable(
#     monkeypatch, tmp_path, status_code
# ):
#     def fake_get(url, stream, timeout):
#         return FakeResponse(status_code=status_code)

#     monkeypatch.setattr(ingestion.requests, "get", fake_get)

#     output_path = tmp_path / "file.parquet"
#     url = "https://example.com/file.parquet"
#     result = ingestion.download_file(url, output_path)

#     assert result is False
#     assert not output_path.exists()


# def test_download_file_success(monkeypatch, tmp_path):
#     def fake_get(url, stream, timeout):
#         assert stream is True
#         assert timeout == ingestion.TIMEOUT
#         return FakeResponse(status_code=200, chunks=[b"part1", b"part2"])

#     monkeypatch.setattr(ingestion.requests, "get", fake_get)

#     output_path = tmp_path / "folder" / "file.parquet"
#     url = "https://example.com/file.parquet"
#     result = ingestion.download_file(url, output_path)

#     assert result is True
#     assert output_path.exists()
#     assert output_path.read_bytes() == b"part1part2"


# def test_download_file_returns_false_on_request_exception(monkeypatch, tmp_path):
#     def fake_get(url, stream, timeout):
#         raise requests.exceptions.Timeout("timeout error")

#     monkeypatch.setattr(ingestion.requests, "get", fake_get)

#     output_path = tmp_path / "file.parquet"
#     url = "https://example.com/file.parquet"
#     result = ingestion.download_file(url, output_path)

#     assert result is False
#     assert not output_path.exists()


# def test_download_file_returns_false_on_http_error(monkeypatch, tmp_path):
#     def fake_get(url, stream, timeout):
#         return FakeResponse(status_code=500, should_raise=True)

#     monkeypatch.setattr(ingestion.requests, "get", fake_get)

#     output_path = tmp_path / "file.parquet"
#     url = "https://example.com/file.parquet"
#     result = ingestion.download_file(url, output_path)

#     assert result is False
#     assert not output_path.exists()


# def test_main_downloads_until_first_missing_file_and_moves_to_next_service(
#     monkeypatch, tmp_path
# ):
#     monkeypatch.chdir(tmp_path)

#     monkeypatch.setattr(ingestion, "YEAR", 2026)
#     monkeypatch.setattr(ingestion, "SERVICE_TYPES", ["yellow", "green"])
#     monkeypatch.setattr(ingestion, "BASE_URL", "https://example.com")

#     def fake_get_last_month_to_download(year):
#         return 4

#     calls = []

#     def fake_download_file(url, output_path):
#         calls.append((url, str(output_path)))

#         if "yellow_tripdata_2026-02.parquet" in url:
#             return False

#         return True

#     monkeypatch.setattr(
#         ingestion,
#         "get_last_month_to_download",
#         fake_get_last_month_to_download,
#     )
#     monkeypatch.setattr(ingestion, "download_file", fake_download_file)

#     ingestion.main()

#     called_urls = [call[0] for call in calls]

#     url = "https://example.com/yellow_tripdata_2026-01.parquet"
#     assert "https://example.com/yellow_tripdata_2026-01.parquet" in called_urls
#     assert "https://example.com/yellow_tripdata_2026-02.parquet" in called_urls
#     assert url not in called_urls

#     assert "https://example.com/green_tripdata_2026-01.parquet" in called_urls
#     assert "https://example.com/green_tripdata_2026-02.parquet" in called_urls
#     assert "https://example.com/green_tripdata_2026-03.parquet" in called_urls


# def test_main_skips_existing_file(monkeypatch, tmp_path):
#     monkeypatch.chdir(tmp_path)

#     monkeypatch.setattr(ingestion, "YEAR", 2026)
#     monkeypatch.setattr(ingestion, "SERVICE_TYPES", ["yellow"])
#     monkeypatch.setattr(ingestion, "BASE_URL", "https://example.com")

#     existing_file = (
#         tmp_path
#         / "data"
#         / "landing"
#         / "yellow_taxi"
#         / "year=2026"
#         / "month=01"
#         / "yellow_tripdata_2026-01.parquet"
#     )
#     existing_file.parent.mkdir(parents=True, exist_ok=True)
#     existing_file.write_bytes(b"already exists")

#     def fake_get_last_month_to_download(year):
#         return 3

#     calls = []

#     def fake_download_file(url, output_path):
#         calls.append(url)
#         return True

#     monkeypatch.setattr(
#         ingestion,
#         "get_last_month_to_download",
#         fake_get_last_month_to_download,
#     )
#     monkeypatch.setattr(ingestion, "download_file", fake_download_file)

#     ingestion.main()

#     assert "https://example.com/yellow_tripdata_2026-01.parquet" not in calls
#     assert "https://example.com/yellow_tripdata_2026-02.parquet" in calls
