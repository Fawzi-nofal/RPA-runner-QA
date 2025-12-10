from __future__ import annotations
import os, time, requests
from typing import Optional

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
GEN_URL  = f"{OLLAMA_HOST}/api/generate"
CHAT_URL = f"{OLLAMA_HOST}/api/chat"
TAGS_URL = f"{OLLAMA_HOST}/api/tags"

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")  # או "llama3:8b"

def _healthcheck(timeout: float = 3.0) -> bool:
    try:
        r = requests.get(TAGS_URL, timeout=timeout)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Ollama] healthcheck failed: {e}")
        return False

def _post_json(url: str, payload: dict, *, timeout_connect=5, timeout_read=30, retries=3, backoff=0.7):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # timeout מחולק: (connect, read)
            r = requests.post(url, json=payload, timeout=(timeout_connect, timeout_read))
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            print(f"[Ollama] POST attempt {attempt}/{retries} failed: {e}")
            time.sleep(backoff * attempt)
    raise last_err  # יתפס ע"י הקריאה העליונה

def chat_simple(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.2,
                timeout: int = 45) -> Optional[str]:
    """
    שימוש ב-/api/generate לקבלת מחרוזת טקסט אחת.
    כולל בדיקת שרת ורטרייז, עם timeouts קצרים כדי שלא "ייתקע".
    """
    if not _healthcheck():
        print(f"[Ollama] server not reachable at {OLLAMA_HOST}")
        return None

    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "stream": False,
    }
    try:
        # timeout_read נגזר מ-timeout הכולל
        data = _post_json(GEN_URL, payload, timeout_connect=5, timeout_read=timeout, retries=3)
        return data.get("response")
    except Exception as e:
        print(f"[Ollama] generate failed: {e}")
        return None

def chat_messages(messages, model: str = DEFAULT_MODEL, temperature: float = 0.2,
                  timeout: int = 45) -> Optional[str]:
    """
    גיבוי ל-/api/chat. לא בשימוש קבוע, אבל נשאיר מסודר.
    """
    if not _healthcheck():
        print(f"[Ollama] server not reachable at {OLLAMA_HOST}")
        return None

    payload = {"model": model, "messages": messages, "temperature": temperature, "stream": False}
    try:
        data = _post_json(CHAT_URL, payload, timeout_connect=5, timeout_read=timeout, retries=3)
        msg = (data.get("message") or {}).get("content")
        return msg
    except Exception as e:
        print(f"[Ollama] chat failed: {e}")
        return None
