"""Tests for download_birds.py pure functions."""

import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from download_birds import slug, wikimedia_search, find_candidates, download_bird, MAX_CLIPS


# ── slug ──────────────────────────────────────────────────────────────────────

def test_slug_spaces_to_underscores():
    assert slug("American Robin") == "american_robin"


def test_slug_hyphens_to_underscores():
    assert slug("Red-tailed Hawk") == "red_tailed_hawk"


def test_slug_already_lowercase():
    assert slug("mallard") == "mallard"


def test_slug_multi_word():
    assert slug("Great Blue Heron") == "great_blue_heron"


# ── wikimedia_search — filters non-audio MIME types ───────────────────────────

def _make_page(title: str, mime: str, url: str = "http://example.com/a.ogg", size: int = 100) -> dict:
    return {
        "title": title,
        "imageinfo": [{"mime": mime, "url": url, "size": size}],
    }


def test_wikimedia_search_keeps_audio_mpeg(monkeypatch):
    pages = {"1": _make_page("Bird.mp3", "audio/mpeg", "http://example.com/1.mp3")}
    monkeypatch.setattr("download_birds.fetch_json", lambda url: {"query": {"pages": pages}})
    results = wikimedia_search("test")
    assert len(results) == 1
    assert results[0]["mime"] == "audio/mpeg"


def test_wikimedia_search_keeps_ogg(monkeypatch):
    pages = {"1": _make_page("Bird.ogg", "audio/ogg", "http://example.com/1.ogg")}
    monkeypatch.setattr("download_birds.fetch_json", lambda url: {"query": {"pages": pages}})
    results = wikimedia_search("test")
    assert len(results) == 1


def test_wikimedia_search_drops_image_mime(monkeypatch):
    pages = {"1": _make_page("Bird.jpg", "image/jpeg", "http://example.com/1.jpg")}
    monkeypatch.setattr("download_birds.fetch_json", lambda url: {"query": {"pages": pages}})
    results = wikimedia_search("test")
    assert results == []


def test_wikimedia_search_prefers_mp3_over_ogg(monkeypatch):
    pages = {
        "1": _make_page("Bird.ogg", "audio/ogg", "http://example.com/1.ogg", size=200),
        "2": _make_page("Bird.mp3", "audio/mpeg", "http://example.com/1.mp3", size=300),
    }
    monkeypatch.setattr("download_birds.fetch_json", lambda url: {"query": {"pages": pages}})
    results = wikimedia_search("test")
    assert results[0]["mime"] == "audio/mpeg"


def test_wikimedia_search_returns_empty_on_exception(monkeypatch):
    monkeypatch.setattr("download_birds.fetch_json", lambda url: (_ for _ in ()).throw(RuntimeError("network")))
    results = wikimedia_search("test")
    assert results == []


# ── find_candidates — deduplicates URLs ───────────────────────────────────────

def test_find_candidates_deduplicates_urls(monkeypatch):
    same_record = {"title": "Bird.mp3", "url": "http://example.com/dup.mp3", "size": 100, "mime": "audio/mpeg"}
    monkeypatch.setattr("download_birds.wikimedia_search", lambda q, limit=8: [same_record])
    monkeypatch.setattr("download_birds.time.sleep", lambda _: None)
    candidates = find_candidates("Mallard")
    urls = [c["url"] for c in candidates]
    assert len(urls) == len(set(urls)), "duplicate URLs found in candidates"


def test_find_candidates_stops_issuing_queries_when_cap_reached(monkeypatch):
    # Each query returns MAX_CLIPS * 4 unique records — cap is hit after first query,
    # so subsequent queries should not be issued.
    call_count = {"n": 0}
    cap = MAX_CLIPS * 4

    def mock_search(q: str, limit: int = 8):
        call_count["n"] += 1
        return [
            {"title": f"Bird{i}.mp3", "url": f"http://example.com/q{call_count['n']}_{i}.mp3", "size": 100, "mime": "audio/mpeg"}
            for i in range(cap)
        ]

    monkeypatch.setattr("download_birds.wikimedia_search", mock_search)
    monkeypatch.setattr("download_birds.time.sleep", lambda _: None)
    find_candidates("Mallard")
    # There are 5 possible queries; after the first fills the cap, no more should run
    assert call_count["n"] == 1


# ── download_bird — skips when already at MAX_CLIPS ───────────────────────────

def test_download_bird_skips_when_full(tmp_path, monkeypatch):
    bird_dir = tmp_path / "mallard"
    bird_dir.mkdir()
    (bird_dir / "1.mp3").write_bytes(b"x")
    (bird_dir / "2.mp3").write_bytes(b"x")

    monkeypatch.setattr("download_birds.OUTPUT_DIR", str(tmp_path))
    find_mock = MagicMock()
    monkeypatch.setattr("download_birds.find_candidates", find_mock)

    result = download_bird("Mallard")

    assert result == MAX_CLIPS
    find_mock.assert_not_called()


def test_download_bird_returns_zero_when_no_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr("download_birds.OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr("download_birds.find_candidates", lambda name: [])

    result = download_bird("Mallard")
    assert result == 0
