"""Tests for pi/local runtime auto-detection (emotionsim.core.runtime)."""
from unittest.mock import patch

import pytest

from emotionsim.core import runtime
from emotionsim.core.config import Settings


@pytest.fixture(autouse=True)
def _reset_runtime_cache():
    runtime.reset_detection()
    yield
    runtime.reset_detection()


@pytest.fixture
def settings():
    return Settings(
        llm_backend="auto",
        vllm_base_url="http://vllm.test:8010",
        ollama_base_url="http://ollama.test:11434/v1",
        ollama_default_model="qwen3.5:4b",
        oracle_db_host="oracle.test",
        oracle_db_port=1522,
        sqlite_db_path="/tmp/rt_test.db",
    )


class TestProbes:
    def test_probe_tcp_unreachable(self):
        # Port 1 on localhost is not listening
        assert runtime.probe_tcp("127.0.0.1", 1, timeout=0.2) is False

    def test_probe_http_conn_error(self):
        with patch("httpx.Client") as MockClient:
            MockClient.side_effect = RuntimeError("conn refused")
            assert runtime.probe_http("http://x", "/v1/models", timeout=0.2) is False

    def test_probe_http_ok(self):
        class _Resp:
            status_code = 200

        seen = {}

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, path):
                seen["path"] = path
                return _Resp()

        with patch("httpx.Client", return_value=_Client()):
            assert runtime.probe_http("http://x", "/v1/models", timeout=0.2) is True
        assert seen["path"] == "http://x/v1/models"


class TestLLMDetection:
    def test_explicit_preference_wins(self, settings):
        with patch("emotionsim.core.config.get_settings", return_value=settings):
            assert runtime.detect_llm_backend("ollama") == "ollama"
            assert runtime.detect_llm_backend("vllm") == "vllm"

    def test_auto_falls_back_to_stub_when_nothing_reachable(self, settings):
        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_vllm", return_value=False):
                with patch("emotionsim.core.runtime.probe_ollama", return_value=False):
                    assert runtime.detect_llm_backend("auto") == "stub"

    def test_auto_prefers_vllm_over_ollama(self, settings):
        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_vllm", return_value=True):
                with patch("emotionsim.core.runtime.probe_ollama", return_value=True):
                    assert runtime.detect_llm_backend("auto") == "vllm"

    def test_auto_prefers_ollama_over_stub(self, settings):
        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_vllm", return_value=False):
                with patch("emotionsim.core.runtime.probe_ollama", return_value=True):
                    assert runtime.detect_llm_backend("auto") == "ollama"

    def test_result_cached(self, settings):
        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_vllm", return_value=True) as pv:
                runtime.detect_llm_backend("auto")
                runtime.detect_llm_backend("auto")
                assert pv.call_count == 1

    def test_router_resolves_auto(self, settings):
        """LLMRouter.get_client(None) must resolve 'auto' to a concrete backend."""
        from emotionsim.llm.router import LLMRouter

        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_vllm", return_value=False):
                with patch("emotionsim.core.runtime.probe_ollama", return_value=False):
                    client = LLMRouter.get_client("auto")
                    assert client.__class__.__name__ == "StubLLMClient"


class TestOllamaModelPick:
    MODELS = [
        "smollm2:135m",
        "qwen2.5:1.5b",
        "qwen3.5:9b",
        "deepseek-v3.2:cloud",
        "nomic-embed-text:latest",
    ]

    def test_preferred_model_kept_when_available(self, settings):
        with patch(
            "emotionsim.core.runtime.list_ollama_models", return_value=self.MODELS
        ):
            assert (
                runtime.pick_ollama_model("qwen2.5:1.5b", settings.ollama_base_url)
                == "qwen2.5:1.5b"
            )

    def test_falls_back_to_any_qwen3(self, settings):
        with patch(
            "emotionsim.core.runtime.list_ollama_models", return_value=self.MODELS
        ):
            assert (
                runtime.pick_ollama_model("qwen3.5:4b", settings.ollama_base_url)
                == "qwen3.5:9b"
            )

    def test_skips_cloud_models(self, settings):
        with patch(
            "emotionsim.core.runtime.list_ollama_models",
            return_value=["deepseek-v3.2:cloud", "gemma3:4b"],
        ):
            assert (
                runtime.pick_ollama_model("qwen3.5:4b", settings.ollama_base_url)
                == "gemma3:4b"
            )

    def test_no_models_returns_preferred(self, settings):
        with patch("emotionsim.core.runtime.list_ollama_models", return_value=[]):
            assert (
                runtime.pick_ollama_model("qwen3.5:4b", settings.ollama_base_url)
                == "qwen3.5:4b"
            )


class TestDatabaseDetection:
    def test_oracle_reachable_keeps_oracle_url(self, settings):
        from emotionsim.core.database import configure_engine
        from emotionsim.core import database as db_mod

        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_oracle", return_value=True):
                url = configure_engine()
        assert url.startswith("oracle+oracledb://")
        assert db_mod._engine_url == url

    def test_oracle_unreachable_falls_back_to_sqlite(self, settings):
        from emotionsim.core.database import configure_engine
        from emotionsim.core import database as db_mod

        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_oracle", return_value=False):
                url = configure_engine()
        assert url.startswith("sqlite+aiosqlite:///")
        assert db_mod._engine_url == url

    def test_configure_engine_is_idempotent(self, settings):
        from emotionsim.core.database import configure_engine, engine
        from emotionsim.core import database as db_mod

        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_oracle", return_value=False):
                configure_engine()
                first = db_mod.engine
                configure_engine()
                assert db_mod.engine is first
        # restore module state for other tests
        db_mod._engine_url = settings.database_url


class TestDoctorReport:
    def test_collect_runtime_report_mocked(self, settings):
        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch("emotionsim.core.runtime.probe_vllm", return_value=False):
                with patch("emotionsim.core.runtime.probe_ollama", return_value=True):
                    with patch(
                        "emotionsim.core.runtime.list_ollama_models",
                        return_value=["qwen3.5:9b", "nomic-embed-text:latest"],
                    ):
                        with patch("emotionsim.core.runtime.probe_oracle", return_value=False):
                            report = runtime.collect_runtime_report(timeout=0.2)

        assert report.ollama_reachable is True
        assert report.resolved_backend == "ollama"
        assert report.ollama_chosen_model == "qwen3.5:9b"
        assert report.database_backend == "sqlite"
        assert report.embedder_present is True


class TestOllamaTagResolution:
    """Bare scenario model_ids (gemma3) must resolve to local tags (gemma3:4b)."""

    def _tags(self):
        return [{"name": "gemma3:4b"}, {"name": "qwen3.5:9b"}, {"name": "smollm2:135m"}]

    def test_exact_tag_passthrough(self):
        from emotionsim.llm.ollama import resolve_ollama_tag, clear_tag_cache

        clear_tag_cache()
        assert resolve_ollama_tag("http://x", "qwen3.5:9b") == "qwen3.5:9b"

    def test_bare_name_resolves_to_family_tag(self):
        from emotionsim.llm.ollama import resolve_ollama_tag, clear_tag_cache

        clear_tag_cache()
        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.get.return_value.status_code = 200
            instance.get.return_value.json.return_value = {"models": self._tags()}
            assert resolve_ollama_tag("http://x", "gemma3") == "gemma3:4b"

    def test_unknown_bare_name_left_as_is(self):
        from emotionsim.llm.ollama import resolve_ollama_tag, clear_tag_cache

        clear_tag_cache()
        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.get.return_value.status_code = 200
            instance.get.return_value.json.return_value = {"models": self._tags()}
            assert resolve_ollama_tag("http://x", "llama2") == "llama2"

    def test_server_down_leaves_name_as_is(self):
        from emotionsim.llm.ollama import resolve_ollama_tag, clear_tag_cache

        clear_tag_cache()
        with patch("httpx.Client", side_effect=RuntimeError("down")):
            assert resolve_ollama_tag("http://x", "gemma3") == "gemma3"


class TestOllamaWrongTagResolution:
    """Code-default tags missing on the server must resolve to family members."""

    TAGS = ["qwen3.5:9b", "gemma3:4b", "smollm2:135m"]

    def _resolve(self, model):
        from emotionsim.llm.ollama import resolve_ollama_tag, clear_tag_cache

        clear_tag_cache()
        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.get.return_value.status_code = 200
            instance.get.return_value.json.return_value = {"models": [{"name": t} for t in self.TAGS]}
            return resolve_ollama_tag("http://x", model)

    def test_missing_version_resolves_to_family_member(self):
        assert self._resolve("qwen3.5:27b") == "qwen3.5:9b"

    def test_existing_version_left_alone(self):
        assert self._resolve("qwen3.5:9b") == "qwen3.5:9b"

    def test_unknown_family_left_alone(self):
        assert self._resolve("llama3:8b") == "llama3:8b"


class TestOllamaGPUProbe:
    def test_cpu_inference_detected(self):
        class _Resp:
            status_code = 200

            def json(self):
                return {"models": [{"name": "qwen3.5:9b", "size_vram": 0}]}

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, path):
                assert path.endswith("/api/ps")
                return _Resp()

        with patch("httpx.Client", return_value=_Client()):
            assert runtime.probe_ollama_gpu("http://x/v1", timeout=0.2) is False

    def test_gpu_inference_detected(self):
        class _Resp:
            status_code = 200

            def json(self):
                return {"models": [{"name": "qwen3.5:9b", "size_vram": 5000000000}]}

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, path):
                return _Resp()

        with patch("httpx.Client", return_value=_Client()):
            assert runtime.probe_ollama_gpu("http://x", timeout=0.2) is True

    def test_empty_ps_is_ok(self):
        class _Resp:
            status_code = 200

            def json(self):
                return {"models": []}

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, path):
                return _Resp()

        with patch("httpx.Client", return_value=_Client()):
            assert runtime.probe_ollama_gpu("http://x", timeout=0.2) is True
