---
name: bedrock
description: AWS Bedrock foundation models for generative AI. Use when invoking foundation models, building AI applications, creating embeddings, configuring model access, or implementing RAG patterns.
last_updated: "2026-01-07"
doc_source: https://docs.aws.amazon.com/bedrock/latest/userguide/
---

# AWS Bedrock

Amazon Bedrock provides access to foundation models (FMs) from AI companies through a unified API. Build generative AI applications with text generation, embeddings, and image generation capabilities.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Common Patterns](#common-patterns)
- [CLI Reference](#cli-reference)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [References](#references)

## Core Concepts

### Foundation Models

Pre-trained models available through Bedrock (from the Bedrock User Guide's model cards; the lineup changes, so check https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html with the AWS documentation tools before choosing):
- **Claude** (Anthropic): text generation, analysis, coding and agents. The current family is Claude 5.5: Opus 5.5 for the most capable reasoning and long-running tasks, Sonnet 5.5 for balanced workloads, Haiku 5.5 for fast, high-volume, low-cost tasks. Claude Fable 5.1 is Anthropic's frontier model for ambitious coding and long-horizon agents. Earlier generations (Claude 5 and 4.x) remain available.
- **Nova** (Amazon): Nova 2 Lite, Nova Pro, Lite and Micro for text, Nova Canvas for images, Nova Multimodal Embeddings
- **Titan Text Embeddings V2** (Amazon) and **Cohere Embed v4**: text embeddings

Where a project routes every model call through one shared library of its own (its project instructions name it), service code calls a model only through that library; the patterns below are what such a library and its callers rest on.

### Model Access

Models must be enabled in your account before use:
- Request access in Bedrock console
- Some models require acceptance of EULAs
- Access is region-specific

### Inference Types

| Type | Use Case | Pricing |
|------|----------|---------|
| **On-Demand** | Variable workloads | Per token |
| **Provisioned Throughput** | Consistent high-volume | Hourly commitment |
| **Batch Inference** | Async large-scale | Discounted per token |

## Common Patterns

Invoke text models through the **Converse API** (`converse`, `converse_stream`): one request format across every model. Use `invoke_model` only for a provider-specific feature Converse does not expose, and for embeddings models, which Converse does not serve (https://docs.aws.amazon.com/bedrock/latest/userguide/apis.html).

- **Always set `inferenceConfig.maxTokens`** on every call.
- **Call models through an inference profile ID** (for example the `us.` geographic or `global.` profile), not a bare in-Region model ID. Look up the current profile IDs with `aws bedrock list-inference-profiles` and the model's card in the Bedrock User Guide; keep the ID in configuration, never hardcoded in handler code. The examples use `us.anthropic.claude-sonnet-5-5`.
- **Retries come from the SDK.** Configure the client with `botocore.config.Config`; never wrap a Bedrock call in a hand-written retry loop. Use adaptive mode for a Bedrock runtime client, because on-demand quotas make it throttle-bound against one resource; every other client uses standard mode (https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html).

### Converse (Text Generation)

**AWS CLI:**

```bash
aws bedrock-runtime converse \
  --model-id us.anthropic.claude-sonnet-5-5 \
  --messages '[{"role": "user", "content": [{"text": "Explain AWS Lambda in 3 sentences."}]}]' \
  --inference-config '{"maxTokens": 1024}' \
  --query 'output.message.content[0].text'
```

**boto3:**

```python
import boto3
from botocore.config import Config

MODEL_ID = "us.anthropic.claude-sonnet-5-5"  # from configuration in real code

bedrock = boto3.client("bedrock-runtime", config=Config(retries={"mode": "adaptive"}))


def converse(prompt: str, max_tokens: int = 1024) -> str:
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    return response["output"]["message"]["content"][0]["text"]
```

### Streaming Response

```python
from collections.abc import Iterator


def stream(prompt: str, max_tokens: int = 1024) -> Iterator[str]:
    response = bedrock.converse_stream(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    for event in response["stream"]:
        if "contentBlockDelta" in event:
            yield event["contentBlockDelta"]["delta"].get("text", "")
```

### Generate Embeddings

Embeddings models are called with `invoke_model`:

```python
import json


def get_embedding(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
    )
    return json.loads(response["body"].read())["embedding"]
```

### Conversation with History

```python
class Conversation:
    def __init__(self, system_prompt: str | None = None) -> None:
        self.messages: list[dict] = []
        self.system = [{"text": system_prompt}] if system_prompt else []

    def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": [{"text": user_message}]})
        response = bedrock.converse(
            modelId=MODEL_ID,
            messages=self.messages,
            system=self.system,
            inferenceConfig={"maxTokens": 1024},
        )
        assistant_message = response["output"]["message"]
        self.messages.append(assistant_message)
        return assistant_message["content"][0]["text"]
```

### List Available Models and Inference Profiles

```bash
# Inference profiles available to the account (use these IDs to invoke)
aws bedrock list-inference-profiles \
  --query 'inferenceProfileSummaries[*].[inferenceProfileId,inferenceProfileName,status]' \
  --output table

# Foundation models by provider
aws bedrock list-foundation-models \
  --by-provider anthropic \
  --query 'modelSummaries[*].[modelId,modelLifecycle.status]'
```

## CLI Reference

### Bedrock (Control Plane)

| Command | Description |
|---------|-------------|
| `aws bedrock list-inference-profiles` | List inference profiles |
| `aws bedrock list-foundation-models` | List available models |
| `aws bedrock get-foundation-model` | Get model details |
| `aws bedrock list-custom-models` | List fine-tuned models |
| `aws bedrock create-model-customization-job` | Start fine-tuning |
| `aws bedrock list-provisioned-model-throughputs` | List provisioned capacity |

### Bedrock Runtime (Data Plane)

| Command | Description |
|---------|-------------|
| `aws bedrock-runtime converse` | Invoke a text model (preferred) |
| `aws bedrock-runtime converse-stream` | Invoke a text model with streaming (preferred) |
| `aws bedrock-runtime invoke-model` | Provider-specific request format; embeddings models |
| `aws bedrock-runtime invoke-model-with-response-stream` | Provider-specific streaming |

### Bedrock Agent Runtime

| Command | Description |
|---------|-------------|
| `aws bedrock-agent-runtime invoke-agent` | Invoke a Bedrock agent |
| `aws bedrock-agent-runtime retrieve` | Query knowledge base |
| `aws bedrock-agent-runtime retrieve-and-generate` | RAG query |

## Best Practices

### Cost Optimization

- **Use appropriate models**: Smaller models for simple tasks
- **Always set maxTokens**: on every call, sized to the expected output
- **Cache responses**: For repeated identical queries
- **Batch when possible**: Use batch inference for bulk processing
- **Monitor usage**: Set up CloudWatch alarms for cost

### Performance

- **Use streaming**: For better user experience with long outputs
- **Connection pooling**: Reuse boto3 clients
- **Regional deployment**: Use closest region to reduce latency
- **Provisioned throughput**: Only for a measured, consistent high-volume workload; it is an hourly commitment billed whatever the traffic, so at low or unmeasured volume on-demand inference is the default

### Security

- **Least privilege IAM**: Only grant needed model access
- **VPC endpoints**: Keep traffic private
- **Guardrails**: Implement content filtering
- **Audit with CloudTrail**: Track model invocations

### IAM Permissions

Invoking through a cross-Region inference profile needs the profile ARN and the foundation-model ARN in every Region the profile routes to:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-sonnet-5-5",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-5-5",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
      ]
    }
  ]
}
```

`converse` and `converse_stream` are authorized by `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`.

## Troubleshooting

### AccessDeniedException

**Causes:**
- Model access not enabled in console
- IAM policy missing `bedrock:InvokeModel`, or missing the foundation-model ARN in a Region the inference profile routes to
- Wrong model ID or region

**Debug:**

```bash
# Check the inference profile exists and is active
aws bedrock get-inference-profile \
  --inference-profile-identifier us.anthropic.claude-sonnet-5-5

# Test IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/my-role \
  --action-names bedrock:InvokeModel \
  --resource-arns "arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-sonnet-5-5"
```

### ModelNotReadyException and ThrottlingException

**Causes:**
- Model still being provisioned or temporarily unavailable
- Exceeded on-demand quota, or too many concurrent requests

**Solutions:**
- Let the SDK retry: adaptive retry mode on the Bedrock runtime client (see Common Patterns); no hand-written loop
- Use a cross-Region or global inference profile to spread load
- Request a quota increase
- Treat `ValidationException` and `AccessDeniedException` as non-retryable: fix the request or the permissions

### ValidationException

**Common issues:**
- Invalid or retired model ID (check the model's lifecycle status)
- Malformed request
- maxTokens exceeds model limit

**Debug:**

```bash
aws bedrock list-foundation-models \
  --by-provider anthropic \
  --query 'modelSummaries[*].[modelId,modelLifecycle.status,inferenceTypesSupported]'
```

## References

- [Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [Bedrock API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/)
- [Bedrock Runtime API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_Operations_Amazon_Bedrock_Runtime.html)
- [Model Parameters](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters.html)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
