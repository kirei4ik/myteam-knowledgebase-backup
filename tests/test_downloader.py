from __future__ import annotations

from pathlib import Path

from app.downloader import Downloader, sha256


class FakeClient:
    def __init__(self, content=b"data"):
        self.content = content

    def download(self, url):
        return self.content


def test_sha256():
    assert sha256(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_downloader_writes_file(tmp_path):
    dl = Downloader(FakeClient(), tmp_path, fail_on_error=False)
    digest = dl.download_to("https://x.ru/a.png", "a.png")
    assert (tmp_path / "a.png").exists()
    assert digest == sha256(b"data")
    assert not dl.errors


def test_downloader_fail_blocks(tmp_path):
    class FailingClient:
        def download(self, url):
            raise RuntimeError("boom")

    dl = Downloader(FailingClient(), tmp_path, fail_on_error=True)
    try:
        dl.download_to("https://x.ru/a.png", "a.png")
        assert False, "should raise"
    except Exception:  # noqa: BLE001
        pass


def test_downloader_fail_nonfatal(tmp_path):
    class FailingClient:
        def download(self, url):
            raise RuntimeError("boom")

    dl = Downloader(FailingClient(), tmp_path, fail_on_error=False)
    assert dl.download_to("https://x.ru/a.png", "a.png") is None
    assert dl.errors
    assert not (tmp_path / "a.png").exists()