"""
Gemini LLM Client wrapper for FDE Assessment 3.
Uses the official google-genai SDK.
Handles API key loading from environment, model cascade failover,
exponential backoff on transient 503/429 errors, and inter-call rate pacing.
"""
from __future__ import annotations

import os
import re
import time
from typing import Optional, List, Set
from dotenv import load_dotenv

load_dotenv()

_CLIENT = None
_EXHAUSTED_MODELS: Set[str] = set()
_LAST_CALL_TIMESTAMP: float = 0.0
_MIN_CALL_SPACING_SECONDS: float = 0.5  # Prevent sub-second bursts on free tier

CANDIDATE_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]


def get_gemini_client():
    """Returns a cached google-genai Client or None if credentials are not configured."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
        
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or not api_key.strip() or "your_gemini_api_key" in api_key:
        return None
        
    try:
        from google import genai
        _CLIENT = genai.Client(api_key=api_key.strip())
        return _CLIENT
    except Exception as exc:
        print(f"[WARN] Failed to initialize Gemini client: {exc}")
        return None


def call_gemini(
    prompt: str,
    system_instruction: str = "",
    model_name: Optional[str] = None,
    max_retries_per_model: int = 2,
) -> Optional[str]:
    """
    Invokes Gemini with the given prompt and system instruction.
    Features:
    - Model cascade: Falls back to secondary Flash/Lite models if quota is exhausted.
    - Exponential backoff on transient errors (503 spikes, temporary 429s).
    - Rate pacing: Enforces minimum interval between consecutive API calls.
    Returns response text or None if all models fail.
    """
    global _LAST_CALL_TIMESTAMP
    client = get_gemini_client()
    if client is None:
        return None

    # Build model cascade list
    configured_model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    models_to_try: List[str] = [configured_model]
    for m in CANDIDATE_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    # Filter out known daily-exhausted models
    available_models = [m for m in models_to_try if m not in _EXHAUSTED_MODELS]
    if not available_models:
        available_models = models_to_try  # Reset if all were marked

    from google.genai import types

    for model in available_models:
        config = types.GenerateContentConfig(
            temperature=0.1,
            system_instruction=system_instruction if system_instruction else None,
        )

        for attempt in range(max_retries_per_model + 1):
            # Enforce minimum inter-call spacing
            now = time.time()
            elapsed = now - _LAST_CALL_TIMESTAMP
            if elapsed < _MIN_CALL_SPACING_SECONDS:
                time.sleep(_MIN_CALL_SPACING_SECONDS - elapsed)

            try:
                _LAST_CALL_TIMESTAMP = time.time()
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    return response.text
                return None
            except Exception as exc:
                err_str = str(exc)
                is_daily_exhausted = "GenerateRequestsPerDay" in err_str or "limit: 20" in err_str
                is_transient = "503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str

                if is_daily_exhausted:
                    print(f"[WARN] Daily quota exhausted for model '{model}'. Failing over to alternate model.")
                    _EXHAUSTED_MODELS.add(model)
                    break  # Break attempt loop and try next model in cascade

                if is_transient and attempt < max_retries_per_model:
                    backoff = (attempt + 1) * 1.5
                    print(f"[WARN] Transient API issue ({err_str[:60]}...). Retrying model '{model}' in {backoff:.1f}s (attempt {attempt + 1}/{max_retries_per_model})...")
                    time.sleep(backoff)
                    continue

                # Non-retryable error or exhausted retries for this model
                print(f"[WARN] Call to model '{model}' failed: {err_str[:80]}")
                break

    return None


def parse_llm_recommendation(
    text: Optional[str],
    fallback_rec: str,
    fallback_next: str
) -> tuple[str, str]:
    """
    Robustly parses recommendation and next step from LLM output.
    Handles markdown bolding, prefixes, multi-line blocks, or freeform text.
    """
    if not text or not text.strip():
        return fallback_rec, fallback_next

    clean_lines = [re.sub(r'[*_#`]', '', l).strip() for l in text.splitlines() if l.strip()]
    rec: Optional[str] = None
    next_s: Optional[str] = None

    for line in clean_lines:
        if re.match(r'^(?:RECOMMENDATION|VERDICT|ADVISORY)[:\-]', line, re.IGNORECASE):
            rec = re.sub(r'^(?:RECOMMENDATION|VERDICT|ADVISORY)[:\-]\s*', '', line, flags=re.IGNORECASE).strip()
        elif re.match(r'^(?:NEXT[ _-]STEP|ACTION|NEXT ACTION)[:\-]', line, re.IGNORECASE):
            next_s = re.sub(r'^(?:NEXT[ _-]STEP|ACTION|NEXT ACTION)[:\-]\s*', '', line, flags=re.IGNORECASE).strip()

    if not rec:
        m = re.search(r'(?:RECOMMENDATION|VERDICT)[:\-]\s*(.+?)(?=(?:NEXT[ _-]STEP|ACTION|\Z))', text, re.IGNORECASE | re.DOTALL)
        if m:
            rec = re.sub(r'[*_#`]', '', m.group(1)).strip()

    if not next_s:
        m = re.search(r'(?:NEXT[ _-]STEP|ACTION)[:\-]\s*(.+?)\Z', text, re.IGNORECASE | re.DOTALL)
        if m:
            next_s = re.sub(r'[*_#`]', '', m.group(1)).strip()

    # Fallback to lines/sentences if structured headers were omitted by the model
    if not rec and clean_lines:
        rec = clean_lines[0]
    if not next_s and len(clean_lines) > 1:
        next_s = clean_lines[1]

    return rec or fallback_rec, next_s or fallback_next
