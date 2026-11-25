
import os
import re

import litellm
from dotenv import load_dotenv
from litellm.caching.caching import Cache
from litellm.exceptions import (
    RateLimitError,
    ServiceUnavailableError,
    InternalServerError,
    APIConnectionError,
    Timeout,
    APIError,
)

# ==========================================
# 1. ENVIRONMENT CONFIGURATION
# ==========================================

load_dotenv()

litellm.suppress_debug_info = True
litellm.cache = Cache(type="local")

GEMINI_MODEL = "gemini/gemini-3.1-flash-lite"
GROQ_MODEL = "groq/openai/gpt-oss-20b"


# ==========================================
# 2. ORDERED API KEY POOL
# ==========================================

def load_key_pool():
    raw_pool = os.getenv("LLM_API_KEYS", "")

    keys = [
        value.strip()
        for value in raw_pool.split(",")
        if value.strip()
    ]

    if len(keys) < 2:
        raise ValueError(
            "LLM_API_KEYS must contain at least two API keys"
        )

    # Reject unresolved environment placeholders.
    for key in keys:
        if re.search(r"\$\{[^}]+\}", key):
            raise ValueError(
                "LLM_API_KEYS contains an unresolved variable"
            )

    return keys


API_KEYS = load_key_pool()

# The provider order matches the key order in .env.
PROVIDER_MODELS = [
    ("gemini", GEMINI_MODEL),
    ("groq", GROQ_MODEL),
]

if len(API_KEYS) != len(PROVIDER_MODELS):
    raise ValueError(
        "The number of API keys must match the "
        "configured provider models"
    )

PROVIDERS = [
    {
        "key_id": f"key_{index + 1}",
        "provider": provider_name,
        "model": model_name,
        "api_key": API_KEYS[index],
    }
    for index, (provider_name, model_name)
    in enumerate(PROVIDER_MODELS)
]


# ==========================================
# 3. CUSTOM EXCEPTION
# ==========================================

class AllProvidersUnavailable(Exception):
    """Raised when all configured providers fail."""
    pass


# ==========================================
# 4. INDIVIDUAL PROVIDER TESTS
# ==========================================

def test_gemini():
    response = litellm.completion(
        model=GEMINI_MODEL,
        api_key=PROVIDERS[0]["api_key"],
        messages=[
            {
                "role": "user",
                "content": "Say hello in one short sentence.",
            }
        ],
        max_tokens=100,
        num_retries=0,
    )
    return response.choices[0].message.content


def test_groq():
    response = litellm.completion(
        model=GROQ_MODEL,
        api_key=PROVIDERS[1]["api_key"],
        messages=[
            {
                "role": "user",
                "content": "Say hello in one short sentence.",
            }
        ],
        max_tokens=100,
        num_retries=0,
    )
    return response.choices[0].message.content


# ==========================================
# 5. FAILOVER AND CACHING
# ==========================================

RETRYABLE_ERRORS = (
    RateLimitError,
    ServiceUnavailableError,
    InternalServerError,
    APIConnectionError,
    Timeout,
)


def generate_with_fallback(messages, simulated_failures=None):
    simulated_failures = simulated_failures or {}
    fallback_attempts = 0

    for provider in PROVIDERS:
        key_id = provider["key_id"]

        # Simulated failures are scoped to this request.
        simulated_status = simulated_failures.get(
            "*",
            simulated_failures.get(key_id),
        )

        if simulated_status in (429, 500, 502, 503):
            fallback_attempts += 1
            continue

        try:
            response = litellm.completion(
                model=provider["model"],
                api_key=provider["api_key"],
                messages=messages,
                max_tokens=256,
                num_retries=0,
                caching=True,
                timeout=8 if key_id == "key_1" else 20,
            )

            hidden_params = (
                getattr(response, "_hidden_params", {})
                or {}
            )
            cache_hit = hidden_params.get("cache_hit") is True

            reply = response.choices[0].message.content

            if not isinstance(reply, str) or not reply.strip():
                fallback_attempts += 1
                continue

            usage = response.usage
            input_tokens = int(
                getattr(usage, "prompt_tokens", 0) or 0
            )
            output_tokens = int(
                getattr(usage, "completion_tokens", 0) or 0
            )

            return {
                "reply": reply,
                "model": provider["model"],
                "resolution_source": (
                    "LLM_CACHE"
                    if cache_hit
                    else "LIVE_INFERENCE"
                ),
                "key_id": None if cache_hit else key_id,
                "fallback_attempts": (
                    0 if cache_hit else fallback_attempts
                ),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

        except RETRYABLE_ERRORS:
            fallback_attempts += 1
            continue

        except APIError as exc:
            # Other HTTP 5xx provider errors are retryable.
            status_code = getattr(exc, "status_code", None)

            if status_code == 429 or (
                isinstance(status_code, int)
                and 500 <= status_code <= 599
            ):
                fallback_attempts += 1
                continue

            raise

    raise AllProvidersUnavailable(
        "all providers unavailable"
    )
