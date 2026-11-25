
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from llm_service import (
    generate_with_fallback,
    AllProvidersUnavailable,
)


def fake_response():
    response = MagicMock()

    response.choices[0].message.content = (
        "Hello from the fallback provider!"
    )

    response.usage.prompt_tokens = 25
    response.usage.completion_tokens = 10
    response._hidden_params = {"cache_hit": False}

    return response


def test_primary_key_failure_uses_backup():
    with patch(
        "llm_service.litellm.completion",
        return_value=fake_response(),
    ) as mock_completion:

        result = generate_with_fallback(
            messages=[
                {"role": "user", "content": "Hello"}
            ],
            simulated_failures={"key_1": 429},
        )

    assert result["key_id"] == "key_2"
    assert result["fallback_attempts"] == 1
    assert result["resolution_source"] == (
        "LIVE_INFERENCE"
    )

    # Primary provider should be skipped.
    assert mock_completion.call_count == 1


def test_all_keys_simulated_failure():
    with patch(
        "llm_service.litellm.completion"
    ) as mock_completion:

        try:
            generate_with_fallback(
                messages=[
                    {"role": "user", "content": "Hello"}
                ],
                simulated_failures={"*": 429},
            )

            assert False, "Expected all providers to fail"

        except AllProvidersUnavailable:
            pass

    # No real provider request should occur.
    mock_completion.assert_not_called()
