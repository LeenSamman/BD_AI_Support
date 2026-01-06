import os
import requests

DEFAULT_LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:1234")
DEFAULT_LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_DEFAULT_MODEL", "").strip()


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def get_local_llm_base_url() -> str:
    return _normalize_base_url(DEFAULT_LOCAL_LLM_BASE_URL)


def get_chat_completions_url(base_url: str | None = None) -> str:
    base = _normalize_base_url(base_url or DEFAULT_LOCAL_LLM_BASE_URL)
    return f"{base}/v1/chat/completions"


def get_default_model_name() -> str:
    return DEFAULT_LOCAL_LLM_MODEL


def fetch_local_models(base_url: str | None = None, timeout: int = 5) -> list[str]:
    base = _normalize_base_url(base_url or DEFAULT_LOCAL_LLM_BASE_URL)
    url = f"{base}/v1/models"
    try:
        response = requests.get(url, timeout=timeout)
    except Exception as exc:
        print(f"Local LLM: models request failed ({exc})")
        return []

    if response.status_code != 200:
        print(f"Local LLM: models request failed ({response.status_code} {response.text})")
        return []

    try:
        payload = response.json()
    except ValueError as exc:
        print(f"Local LLM: models response not JSON ({exc})")
        return []

    models: list[str] = []
    if isinstance(payload, dict):
        data = payload.get("data", [])
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    model_id = entry.get("id")
                    if model_id:
                        models.append(str(model_id).strip())
                elif isinstance(entry, str):
                    models.append(entry.strip())

    deduped: list[str] = []
    seen = set()
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        deduped.append(model)
    return deduped
