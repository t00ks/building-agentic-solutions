from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from langchain_aws import ChatBedrockConverse
from langchain_openai import AzureChatOpenAI
from openai import AzureOpenAI

from core.config import get_config
from core.exceptions import AgentResourceError
from core.logging_config import get_logger

config = get_config()
logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_boto_client():
    try:
        return boto3.client(
            "bedrock-runtime",
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key,
            config=Config(
                max_pool_connections=50,
                retries={"mode": "standard", "max_attempts": 8},
            ),
        )
    except Exception as e:
        raise AgentResourceError("Failed to initialize Bedrock client") from e


@lru_cache(maxsize=1)
def get_azure_openai_client():
    try:
        return AzureOpenAI(api_version="2024-12-01-preview", azure_endpoint=config.azure.openai_embedding_endpoint, api_key=config.azure.openai_key)
    except Exception as e:
        raise AgentResourceError("Failed to initialize Azure OpenAI client") from e


@lru_cache(maxsize=1)
def get_llm() -> Any:
    if config.hyperscaler == "AWS":
        return get_bedrock_llm()
    elif config.hyperscaler == "AZURE":
        return get_azure_openai_llm()
    else:
        raise AgentResourceError(f"Unsupported hyperscaler: {config.hyperscaler}")


@lru_cache(maxsize=1)
def get_bedrock_llm() -> ChatBedrockConverse:
    client = get_boto_client()

    return ChatBedrockConverse(
        model=config.aws.model_id,
        region_name=config.aws.region,
        temperature=config.llm.agent_temperature,
        max_tokens=2048,
        client=client,
    )


@lru_cache(maxsize=1)
def get_azure_openai_llm():
    return AzureChatOpenAI(
        azure_endpoint=config.azure.openai_model_endpoint,
        api_key=config.azure.openai_key,
        azure_deployment=config.azure.model_deployment,
        api_version="2024-02-01",
        temperature=config.llm.agent_temperature,
        max_tokens=2048,
    )