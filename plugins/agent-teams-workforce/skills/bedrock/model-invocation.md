# Bedrock Model Invocation Patterns

Advanced patterns for invoking foundation models. Prefer the Converse API (below) for text models; the provider-specific `invoke_model` bodies in the next section are for features Converse does not expose and for embeddings. The model IDs are examples: models are retired and replaced, so look up the current ID and inference profile on the model's card in the Bedrock User Guide (https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html) and keep it in configuration. Amazon Titan Text and Stability AI models shown here may no longer be offered; the current Amazon text and image models are the Nova family. Where the project names one shared library for model calls, service code calls a model only through it.

## Model-Specific Invocation

### Claude (Anthropic)

```python
import boto3
import json

bedrock = boto3.client("bedrock-runtime")


def invoke_claude(messages, system=None, max_tokens=1024, temperature=1.0):
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }

    if system:
        body["system"] = system

    response = bedrock.invoke_model(
        modelId="us.anthropic.claude-sonnet-5-5",
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    return json.loads(response["body"].read())


# Text generation
result = invoke_claude(
    messages=[{"role": "user", "content": "Explain microservices."}],
    system="You are a software architect. Be concise.",
    temperature=0.7,
)

# With image (Claude 3 vision)
import base64

with open("diagram.png", "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode()

result = invoke_claude(
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                {"type": "text", "text": "Describe this architecture diagram."},
            ],
        }
    ]
)
```

### Titan Text (Amazon)

```python
def invoke_titan_text(prompt, max_tokens=512, temperature=0.7):
    response = bedrock.invoke_model(
        modelId="amazon.titan-text-express-v1",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": temperature,
                "topP": 0.9,
                "stopSequences": [],
            },
        }),
    )

    result = json.loads(response["body"].read())
    return result["results"][0]["outputText"]
```

### Titan Embeddings (Amazon)

```python
def invoke_titan_embeddings(text, dimensions=1024):
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text, "dimensions": dimensions, "normalize": True}),
    )

    result = json.loads(response["body"].read())
    return result["embedding"]


# Batch embeddings
def batch_embeddings(texts, dimensions=1024):
    embeddings = []
    for text in texts:
        embedding = invoke_titan_embeddings(text, dimensions)
        embeddings.append(embedding)
    return embeddings
```

### Claude Haiku (Anthropic)

Fast, cost-efficient text generation for simple, high-volume tasks.

```python
def invoke_claude_haiku(prompt, max_tokens=512, temperature=0.7):
    response = bedrock.invoke_model(
        modelId="us.anthropic.claude-haiku-5-5",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]
```

### Stable Diffusion (Image Generation)

```python
import base64


def generate_image(prompt, negative_prompt="", cfg_scale=7, seed=0):
    response = bedrock.invoke_model(
        modelId="stability.stable-diffusion-xl-v1",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "text_prompts": [{"text": prompt, "weight": 1.0}, {"text": negative_prompt, "weight": -1.0}],
            "cfg_scale": cfg_scale,
            "seed": seed,
            "steps": 50,
            "width": 1024,
            "height": 1024,
        }),
    )

    result = json.loads(response["body"].read())
    image_data = base64.b64decode(result["artifacts"][0]["base64"])

    with open("output.png", "wb") as f:
        f.write(image_data)

    return "output.png"
```

## Converse API (Unified)

The Converse API provides a unified interface across models.

```python
def converse(messages, model_id, system=None, max_tokens=1024):
    params = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.7},
    }

    if system:
        params["system"] = [{"text": system}]

    response = bedrock.converse(**params)
    return response["output"]["message"]["content"][0]["text"]


# Works with any supported model
result = converse(
    messages=[{"role": "user", "content": [{"text": "What is Lambda?"}]}],
    model_id="us.anthropic.claude-sonnet-5-5",
    system="Be concise.",
)
```

### Converse with Tool Use

```python
def converse_with_tools(messages, tools, model_id):
    response = bedrock.converse(modelId=model_id, messages=messages, toolConfig={"tools": tools})

    output = response["output"]["message"]

    # Check if model wants to use a tool
    if response["stopReason"] == "tool_use":
        tool_use = next(block for block in output["content"] if "toolUse" in block)
        return {
            "tool_name": tool_use["toolUse"]["name"],
            "tool_input": tool_use["toolUse"]["input"],
            "tool_use_id": tool_use["toolUse"]["toolUseId"],
        }

    return {"text": output["content"][0]["text"]}


# Define tools
tools = [
    {
        "toolSpec": {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {"location": {"type": "string", "description": "City name"}},
                    "required": ["location"],
                }
            },
        }
    }
]

# Invoke
result = converse_with_tools(
    messages=[{"role": "user", "content": [{"text": "What is the weather in Seattle?"}]}],
    tools=tools,
    model_id="us.anthropic.claude-sonnet-5-5",
)
```

## RAG with Knowledge Bases

```python
bedrock_agent = boto3.client("bedrock-agent-runtime")


def rag_query(query, knowledge_base_id, model_arn):
    response = bedrock_agent.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": knowledge_base_id,
                "modelArn": model_arn,
                "retrievalConfiguration": {"vectorSearchConfiguration": {"numberOfResults": 5}},
            },
        },
    )

    return {"answer": response["output"]["text"], "citations": response.get("citations", [])}


# Usage
result = rag_query(
    query="How do I configure S3 bucket policies?",
    knowledge_base_id="KNOWLEDGE_BASE_ID",
    model_arn="arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-sonnet-5-5",
)
```

### Retrieve Only (No Generation)

```python
def retrieve_context(query, knowledge_base_id, num_results=5):
    response = bedrock_agent.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": num_results}},
    )

    return [
        {"text": result["content"]["text"], "score": result["score"], "source": result["location"]}
        for result in response["retrievalResults"]
    ]
```

## Guardrails

```python
def invoke_with_guardrails(prompt, guardrail_id, guardrail_version):
    response = bedrock.invoke_model(
        modelId="us.anthropic.claude-sonnet-5-5",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }),
        guardrailIdentifier=guardrail_id,
        guardrailVersion=guardrail_version,
    )

    result = json.loads(response["body"].read())

    # Check if guardrail intervened
    if "amazon-bedrock-guardrailAction" in response["ResponseMetadata"]["HTTPHeaders"]:
        return {"blocked": True, "reason": "Content policy violation"}

    return {"blocked": False, "text": result["content"][0]["text"]}
```

## Batch Inference

```python
import time

import boto3

bedrock = boto3.client("bedrock")


def create_batch_job(input_s3_uri, output_s3_uri, model_id, role_arn):
    response = bedrock.create_model_invocation_job(
        jobName=f"batch-job-{int(time.time())}",
        modelId=model_id,
        roleArn=role_arn,
        inputDataConfig={"s3InputDataConfig": {"s3Uri": input_s3_uri}},
        outputDataConfig={"s3OutputDataConfig": {"s3Uri": output_s3_uri}},
    )

    return response["jobArn"]


# Input format (JSONL file in S3)
# {"recordId": "1", "modelInput": {"anthropic_version": "...", "messages": [...]}}
# {"recordId": "2", "modelInput": {"anthropic_version": "...", "messages": [...]}}
```

## Error Handling

Retries come from the SDK: configure the client with `botocore.config.Config` and never wrap a Bedrock call in a hand-written retry loop. Use adaptive mode for a Bedrock runtime client, because on-demand quotas make it throttle-bound against one resource (https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html). `ThrottlingException` is retried by the SDK; `ValidationException` and `AccessDeniedException` are not retryable, so fix the request or the permissions.

```python
import json

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

bedrock = boto3.client("bedrock-runtime", config=Config(retries={"mode": "adaptive"}))


def invoke(model_id: str, body: dict) -> dict:
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ModelNotReadyException":
            raise RuntimeError(f"Model {model_id} is not ready; retry the request later") from error
        raise
    return json.loads(response["body"].read())
```

## Provisioned Throughput

Provisioned Throughput is billed per model unit per hour for the commitment term, whatever the traffic. It is not a default at low or unmeasured volume: use on-demand inference through an inference profile, and choose Provisioned Throughput only for a stated, measured need, recording the cost comparison. Check the model's card for whether it supports Provisioned Throughput; it is created for a base model ID (not an inference profile), and the provisioned model's ARN is then passed as `modelId`.

## VPC Endpoint

Code that runs inside a VPC reaches Bedrock through an interface VPC endpoint defined in the project's CDK. Use the VPC the project's networking stack provides (for example through the SSM parameters it publishes) rather than creating one; the project's architecture names how stacks share it.

```python
from aws_cdk import aws_ec2 as ec2

vpc.add_interface_endpoint(
    "BedrockRuntimeEndpoint",
    service=ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
    private_dns_enabled=True,
    subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
)
```
