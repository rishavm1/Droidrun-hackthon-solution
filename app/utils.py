import re
import os
import logging

try:
    import requests
except ImportError:
    requests = None

def parse_budget(raw: str) -> float:
    """Parse a user-supplied budget string into a positive float.

    Supports formats like:
      - "14,999"
      - "14999"
      - "15k" or "15K" -> 15000
      - "2.5m" or "2.5M" -> 2500000
    Raises ValueError on failure.
    """
    if raw is None:
        raise ValueError("No budget provided")
    s = str(raw).strip()
    if s == "":
        raise ValueError("No budget provided")

    # Support suffixes k/K and m/M
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmM])?\s*$", s.replace(',', ''))
    if not m:
        # Fallback: strip anything except digits and dot
        cleaned = re.sub(r"[^0-9.]", "", s)
        if cleaned == "":
            raise ValueError(f"Could not parse budget from '{raw}'")
        try:
            val = float(cleaned)
        except ValueError:
            raise ValueError(f"Could not parse budget from '{raw}'")
        if val <= 0:
            raise ValueError("Budget must be positive")
        return val

    num = float(m.group(1))
    suffix = m.group(2)
    if suffix:
        if suffix.lower() == 'k':
            num *= 1_000
        elif suffix.lower() == 'm':
            num *= 1_000_000

    if num <= 0:
        raise ValueError("Budget must be positive")
    return float(num)


def gemini_query(prompt: str, max_tokens: int = 400) -> str:
    """Optional Gemini (LLM) wrapper.

    Returns a string result or a concise error message.
    """
    endpoint = os.getenv("GEMINI_ENDPOINT")
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not endpoint or not api_key:
        return "Gemini not configured. Set GEMINI_ENDPOINT and GEMINI_API_KEY."
    if requests is None:
        return "Python package 'requests' is not installed."

    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "max_tokens": max_tokens}
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Try several common places for returned text
        if isinstance(data, dict):
            text = data.get("text") or data.get("output") or data.get("response")
            if not text:
                choices = data.get("choices")
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    text = first.get("text") or first.get("message") or first.get("content")
            if isinstance(text, (list, dict)):
                return str(text)
            return text or str(data)
        return str(data)
    except requests.RequestException as e:
        logging.error(f"Request error calling Gemini: {e}")
        return f"Request error calling Gemini endpoint: {e}"
    except ValueError as e:
        logging.error(f"JSON parsing error: {e}")
        return f"JSON parsing error from Gemini endpoint: {e}"
    except Exception as e:
        logging.error(f"Unexpected error calling Gemini: {e}")
        return f"Error calling Gemini endpoint: {e}"