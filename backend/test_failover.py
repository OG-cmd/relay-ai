
from llm_service import (
    generate_with_fallback,
    AllProvidersUnavailable
)

try:
    generate_with_fallback(
        messages=[
            {"role": "user", "content": "Hello"}
        ],
        simulated_failures={"*": 429}
    )

    print("FAIL: Expected an exception")

except AllProvidersUnavailable as e:
    print("PASS:", str(e))
