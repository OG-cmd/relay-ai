
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from llm_service import generate_with_fallback


def make_response(cache_hit):
    response = MagicMock()

    response.choices[0].message.content = (
        "The capital of Japan is Tokyo."
    )

    response.usage.prompt_tokens = 88
    response.usage.completion_tokens = 42

    response._hidden_params = {
        "cache_hit": cache_hit
    }

    return response


def test_live_inference_metadata():
    with patch(
        "llm_service.litellm.completion",
        return_value=make_response(False),
    ):
        result = generate_with_fallback(
            messages=[
                {
                    "role": "user",
                    "content": "What is the capital of Japan?"
                }
            ]
        )

    assert result["resolution_source"] == (
        "LIVE_INFERENCE"
    )
    assert result["key_id"] == "key_1"
    assert result["fallback_attempts"] == 0
    assert result["input_tokens"] == 88
    assert result["output_tokens"] == 42


def test_cached_response_metadata():
    with patch(
        "llm_service.litellm.completion",
        return_value=make_response(True),
    ):
        result = generate_with_fallback(
            messages=[
                {
                    "role": "user",
                    "content": "What is the capital of Japan?"
                }
            ]
        )

    assert result["resolution_source"] == (
        "LLM_CACHE"
    )
    assert result["key_id"] is None
    assert result["fallback_attempts"] == 0
    assert result["input_tokens"] == 88
    assert result["output_tokens"] == 42
    assert result["reply"] == (
        "The capital of Japan is Tokyo."
    )


def test_cache_after_primary_failure():
    with patch(
        "llm_service.litellm.completion",
        return_value=make_response(True),
    ) as mock_completion:
        result = generate_with_fallback(
            messages=[
                {
                    "role": "user",
                    "content": "What is the capital of Japan?"
                }
            ],
            simulated_failures={"key_1": 429},
        )

    assert result["resolution_source"] == "LLM_CACHE"
    assert result["key_id"] is None
    assert result["fallback_attempts"] == 0

    # The primary provider was skipped.
    assert mock_completion.call_count == 1
