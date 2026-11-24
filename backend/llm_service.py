
import os

import litellm
from dotenv import load_dotenv
from litellm.caching.caching import Cache
from litellm.exceptions import (
    RateLimitError,
    ServiceUnavailableError,
    InternalServerError,
    APIConnectionError,
)

# ==========================================
# 1. ENVIRONMENT AND CACHE CONFIGURATION
# ==========================================

load_dotenv()

litellm.suppress_debug_info = True

# LiteLLM built-in local response cache
litellm.cache = Cache(type="local")


# ==========================================
# 2. MODEL CONFIGURATION
# ==========================================

GEMINI_MODEL = "gemini/gemini-3.1-flash-lite"
GROQ_MODEL = "groq/openai/gpt-oss-20b"


# ==========================================
# 3. PROVIDER POOL
# ==========================================

PROVIDERS = [
    {
        "key_id": "key_1",
        "provider": "gemini",
        "model": GEMINI_MODEL,
        "api_key": os.getenv("GEMINI_API_KEY"),
    },
    {
        "key_id": "key_2",
        "provider": "groq",
        "model": GROQ_MODEL,
        "api_key": os.getenv("GROQ_API_KEY"),
    },
]


# ==========================================
# 4. CUSTOM EXCEPTION
# ==========================================

class AllProvidersUnavailable(Exception):
    """Raised when all configured providers fail."""
    pass


# ==========================================
# 5. INDIVIDUAL PROVIDER TESTS
# ==========================================

def test_gemini():
    response = litellm.completion(
        model=GEMINI_MODEL,
        api_key=os.getenv("GEMINI_API_KEY"),
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
        api_key=os.getenv("GROQ_API_KEY"),
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
# 6. AUTOMATIC FAILOVER AND CACHING
# ==========================================

def generate_with_fallback(messages, simulated_failures=None):
    """
    Generate an AI response using the provider pool.

    Features:
    - Automatic provider fallback
    - Simulated provider failures
    - LiteLLM response caching
    - Cache-hit detection
    - Per-request token usage
    """

    simulated_failures = simulated_failures or {}
    fallback_attempts = 0

    for provider in PROVIDERS:

        # --------------------------------------
        # A. CHECK SIMULATED FAILURES
        # --------------------------------------

        if "*" in simulated_failures:
            simulated_status = simulated_failures["*"]
        else:
            simulated_status = simulated_failures.get(
                provider["key_id"]
            )

        if simulated_status in (429, 500, 502, 503):
            fallback_attempts += 1
            continue

        try:

            # ----------------------------------
            # B. CALL LITELLM WITH CACHING
            # ----------------------------------

            response = litellm.completion(
                model=provider["model"],
                api_key=provider["api_key"],
                messages=messages,
                max_tokens=256,
                num_retries=0,
                caching=True,
            )

            # ----------------------------------
            # C. DETECT CACHE HIT
            # ----------------------------------

            hidden_params = (
                getattr(response, "_hidden_params", {})
                or {}
            )

            cache_hit = (
                hidden_params.get("cache_hit", False)
                is True
            )

            # ----------------------------------
            # D. EXTRACT RESPONSE DATA
            # ----------------------------------

            reply = response.choices[0].message.content

            if not reply or not reply.strip():
                raise ValueError(
                    "Provider returned an empty response"
                )

            input_tokens = int(
                response.usage.prompt_tokens
            )

            output_tokens = int(
                response.usage.completion_tokens
            )

            # ----------------------------------
            # E. RETURN RESPONSE METADATA
            # ----------------------------------

            return {
                "reply": reply,
                "model": provider["model"],
                "resolution_source": (
                    "LLM_CACHE"
                    if cache_hit
                    else "LIVE_INFERENCE"
                ),
                "key_id": (
                    None
                    if cache_hit
                    else provider["key_id"]
                ),
                "fallback_attempts": (
                    0
                    if cache_hit
                    else fallback_attempts
                ),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

        # --------------------------------------
        # F. RETRYABLE PROVIDER ERRORS
        # --------------------------------------

        except (
            RateLimitError,
            ServiceUnavailableError,
            InternalServerError,
            APIConnectionError,
        ):
            fallback_attempts += 1
            continue

    # ------------------------------------------
    # G. ALL PROVIDERS UNAVAILABLE
    # ------------------------------------------

    raise AllProvidersUnavailable(
        "all providers unavailable"
    )
