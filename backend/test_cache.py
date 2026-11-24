
import time

import litellm
from llm_service import GROQ_MODEL, PROVIDERS

# Use the existing LiteLLM cache configuration.
groq_key = PROVIDERS[1]["api_key"]

messages = [
    {
        "role": "system",
        "content": "You are a helpful AI assistant."
    },
    {
        "role": "user",
        "content": "What is the capital of France?"
    }
]


def make_request():
    start = time.perf_counter()

    response = litellm.completion(
        model=GROQ_MODEL,
        api_key=groq_key,
        messages=messages,
        max_tokens=256,
        num_retries=0,
        caching=True
    )

    latency = round(
        (time.perf_counter() - start) * 1000
    )

    return response, latency


print("First request:")
first, first_latency = make_request()

print("Reply:", first.choices[0].message.content)
print("Latency:", first_latency, "ms")
print("Usage:", first.usage)

print("\nSecond request:")
second, second_latency = make_request()

print(
    "First response hidden metadata:",
    getattr(first, "_hidden_params", {})
)

print(
    "Second response hidden metadata:",
    getattr(second, "_hidden_params", {})
)


print("Reply:", second.choices[0].message.content)
print("Latency:", second_latency, "ms")
print("Usage:", second.usage)

print("\nComparison:")
print(
    "Identical replies:",
    first.choices[0].message.content
    == second.choices[0].message.content
)
print(
    "Second request faster:",
    second_latency < first_latency
)

print("\nAdditional cache performance tests:")

for i in range(5):
    response, latency = make_request()

    print(
        f"Request {i + 3}: "
        f"{latency} ms"
    )
