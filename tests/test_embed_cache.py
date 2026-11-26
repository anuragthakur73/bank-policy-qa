# Week 5 S3: on-disk embedding cache (EMBED_CACHE) makes eval retrieval repeatable. No network: the remote call is faked.
import json
import app.retrieve as r

def _fresh(monkeypatch, tmp_path, vectors):
    calls = []
    def fake_remote(q):
        calls.append(q)
        return vectors[len(calls) - 1]
    monkeypatch.setattr(r, "_embed_remote", fake_remote)
    monkeypatch.setattr(r, "_EMBED_CACHE", {})
    monkeypatch.setattr(r, "EMBED_STATS", {"hit": 0, "miss": 0})
    path = tmp_path / "cache" / "emb.jsonl"
    monkeypatch.setenv("EMBED_CACHE", str(path))
    return calls, path

def test_second_call_reuses_first_vector(monkeypatch, tmp_path):
    # the remote would return a slightly different vector the second time, as text-embedding-3-small can
    calls, _ = _fresh(monkeypatch, tmp_path, [[0.2993, 0.1], [0.302, 0.1]])
    assert r._embed("Can the grandfather join?") == [0.2993, 0.1]
    assert r._embed("Can the grandfather join?") == [0.2993, 0.1]
    assert len(calls) == 1 and r.EMBED_STATS == {"hit": 1, "miss": 1}

def test_cache_survives_a_new_process_and_stores_no_question_text(monkeypatch, tmp_path):
    calls, path = _fresh(monkeypatch, tmp_path, [[1.0, 2.0]])
    r._embed("PAN ABCDE1234F loan?")
    text = path.read_text(encoding="utf-8")
    assert "ABCDE1234F" not in text and "loan" not in text
    row = json.loads(text.splitlines()[0])
    assert row["key"] == r._cache_key("PAN ABCDE1234F loan?") and row["vector"] == [1.0, 2.0]
    monkeypatch.setattr(r, "_EMBED_CACHE", {})            # as if a second eval run started
    monkeypatch.setattr(r, "_embed_remote", lambda q: (_ for _ in ()).throw(AssertionError("should not call")))
    assert r._embed("PAN ABCDE1234F loan?") == [1.0, 2.0]

def test_different_questions_are_embedded_separately(monkeypatch, tmp_path):
    calls, _ = _fresh(monkeypatch, tmp_path, [[1.0], [2.0]])
    assert r._embed("a") == [1.0] and r._embed("b") == [2.0] and len(calls) == 2

def test_off_without_env(monkeypatch, tmp_path):
    calls, path = _fresh(monkeypatch, tmp_path, [[1.0], [2.0]])
    monkeypatch.delenv("EMBED_CACHE")
    r._embed("a"); r._embed("a")
    assert len(calls) == 2 and not path.exists()
