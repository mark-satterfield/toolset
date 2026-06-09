# LLM Integration Guide

Production patterns for integrating Large Language Models into applications.

---

## Table of Contents

- [API Integration Patterns](#api-integration-patterns)
- [Prompt Engineering](#prompt-engineering)
- [Token Optimization](#token-optimization)
- [Cost Management](#cost-management)
- [Error Handling](#error-handling)

---

## API Integration Patterns

### Provider Abstraction Layer

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    def chat(self, messages: List[Dict], **kwargs) -> str:
        pass

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        kwargs.setdefault("max_tokens", 16000)
        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.content[0].text

    def chat(self, messages: List[Dict], **kwargs) -> str:
        kwargs.setdefault("max_tokens", 16000)
        response = self.client.messages.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return response.content[0].text

class BedrockProvider(LLMProvider):
    """Claude via Amazon Bedrock — AWS-native alternative/fallback provider."""

    def __init__(self, model: str = "anthropic.claude-sonnet-4-6", region: str = "us-east-1"):
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.model = model

    def complete(self, prompt: str, **kwargs) -> str:
        response = self.client.converse(
            modelId=self.model,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
        )
        return response["output"]["message"]["content"][0]["text"]
```

### Retry and Fallback Strategy

```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def call_llm_with_retry(provider: LLMProvider, prompt: str) -> str:
    """Call LLM with exponential backoff retry."""
    return provider.complete(prompt)

def call_with_fallback(
    primary: LLMProvider,
    fallback: LLMProvider,
    prompt: str
) -> str:
    """Try primary provider, fall back on failure."""
    try:
        return call_llm_with_retry(primary, prompt)
    except Exception as e:
        logger.warning(f"Primary provider failed: {e}, using fallback")
        return call_llm_with_retry(fallback, prompt)
```

---

## Prompt Engineering

### Prompt Templates

| Pattern | Use Case | Structure |
|---------|----------|-----------|
| Zero-shot | Simple tasks | Task description + input |
| Few-shot | Complex tasks | Examples + task + input |
| Chain-of-thought | Reasoning | "Think step by step" + task |
| Role-based | Specialized output | System role + task |

### Few-Shot Template

```python
FEW_SHOT_TEMPLATE = """
You are a sentiment classifier. Classify the sentiment as positive, negative, or neutral.

Examples:
Input: "This product is amazing, I love it!"
Output: positive

Input: "Terrible experience, waste of money."
Output: negative

Input: "The product arrived on time."
Output: neutral

Now classify:
Input: "{user_input}"
Output:"""

def classify_sentiment(text: str, provider: LLMProvider) -> str:
    prompt = FEW_SHOT_TEMPLATE.format(user_input=text)
    response = provider.complete(prompt, max_tokens=10, temperature=0)
    return response.strip().lower()
```

### System Prompts for Consistency

```python
SYSTEM_PROMPT = """You are a helpful assistant that answers questions about our product.

Guidelines:
- Be concise and direct
- Use bullet points for lists
- If unsure, say "I don't have that information"
- Never make up information
- Keep responses under 200 words

Product context:
{product_context}
"""

def create_chat_messages(user_query: str, context: str) -> List[Dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(product_context=context)},
        {"role": "user", "content": user_query}
    ]
```

---

## Token Optimization

### Token Counting

```python
from anthropic import Anthropic

client = Anthropic()

def count_tokens(text: str, model: str = "claude-sonnet-4-6") -> int:
    """Count tokens for a given text and model."""
    response = client.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": text}],
    )
    return response.input_tokens

def truncate_to_token_limit(text: str, max_tokens: int, model: str = "claude-sonnet-4-6") -> str:
    """Truncate text to fit within a token limit."""
    tokens = count_tokens(text, model)

    while tokens > max_tokens:
        text = text[: int(len(text) * max_tokens / tokens * 0.95)]
        tokens = count_tokens(text, model)

    return text
```

### Context Window Management

| Model | Context Window | Effective Limit |
|-------|----------------|-----------------|
| Claude Opus 4.8 | 1,000,000 | ~900,000 (leave room for response) |
| Claude Sonnet 4.6 | 1,000,000 | ~900,000 |
| Claude Haiku 4.5 | 200,000 | ~180,000 |

### Chunking Strategy

```python
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks
```

---

## Cost Management

### Cost Calculation

| Model | Input Cost | Output Cost | Example (1M in + 1M out) |
|-------|------------|-------------|--------------------------|
| Claude Opus 4.8 | $5.00/1M | $25.00/1M | $30.00 |
| Claude Sonnet 4.6 | $3.00/1M | $15.00/1M | $18.00 |
| Claude Haiku 4.5 | $1.00/1M | $5.00/1M | $6.00 |

### Cost Tracking

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int
    model: str
    cost: float

def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str
) -> float:
    """Calculate cost based on token usage."""
    PRICING = {  # USD per 1M tokens
        "claude-opus-4-8": {"input": 5.00, "output": 25.00},
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    }

    prices = PRICING.get(model, {"input": 3.00, "output": 15.00})

    input_cost = (input_tokens / 1_000_000) * prices["input"]
    output_cost = (output_tokens / 1_000_000) * prices["output"]

    return input_cost + output_cost
```

### Cost Optimization Strategies

1. **Use smaller models for simple tasks** - Haiku 4.5 for classification, Opus 4.8 for frontier reasoning
2. **Cache common responses** - Store results for repeated queries
3. **Batch requests** - Combine multiple items in single prompt
4. **Truncate context** - Only include relevant information
5. **Set max_tokens limit** - Prevent runaway responses

---

## Error Handling

### Common Error Types

| Error | Cause | Handling |
|-------|-------|----------|
| RateLimitError | Too many requests | Exponential backoff |
| InvalidRequestError | Bad input | Validate before sending |
| AuthenticationError | Invalid API key | Check credentials |
| ServiceUnavailable | Provider down | Fallback to alternative |
| ContextLengthExceeded | Input too long | Truncate or chunk |

### Error Handling Pattern

```python
from anthropic import RateLimitError, APIStatusError

def safe_llm_call(provider: LLMProvider, prompt: str, max_retries: int = 3) -> str:
    """Safely call LLM with comprehensive error handling."""
    for attempt in range(max_retries):
        try:
            return provider.complete(prompt)

        except RateLimitError:
            wait_time = 2 ** attempt
            logger.warning(f"Rate limited, waiting {wait_time}s")
            time.sleep(wait_time)

        except APIStatusError as e:
            if e.status_code >= 500:
                logger.warning(f"Server error: {e}, retrying...")
                time.sleep(1)
            else:
                raise

    raise Exception(f"Failed after {max_retries} attempts")
```

### Response Validation

```python
import json
from pydantic import BaseModel, ValidationError

class StructuredResponse(BaseModel):
    answer: str
    confidence: float
    sources: List[str]

def parse_structured_response(response: str) -> StructuredResponse:
    """Parse and validate LLM JSON response."""
    try:
        data = json.loads(response)
        return StructuredResponse(**data)
    except json.JSONDecodeError:
        raise ValueError("Response is not valid JSON")
    except ValidationError as e:
        raise ValueError(f"Response validation failed: {e}")
```
