"""
Centralised configuration management for the application.

This module handles loading and validation of all environment variables used across
the application, providing a single source of truth for configuration.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .exceptions import AgentConfigurationError


@dataclass(frozen=True)
class AWSConfig:
    """AWS-related configuration."""

    region: str
    model_id: str | None = None
    embedding_model_id: str | None = None
    s3_bucket_name: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None


@dataclass(frozen=True)
class AzureConfig:
    """Azure-related configuration."""

    openai_model_endpoint: str | None = None
    openai_embedding_endpoint: str | None = None
    openai_key: str | None = None
    text_embedding_deployment: str | None = None
    model_deployment: str | None = None
    speech_api_key: str | None = None
    speech_region: str | None = None
    speech_endpoint: str | None = None  # Custom Azure OpenAI endpoint for speech services
    speech_tts_deployment: str | None = None
    speech_stt_deployment: str | None = None


@dataclass(frozen=True)
class DatabaseConfig:
    """Database-related configuration."""

    postgres_uri: str
    document_table: str = "document_vectors"
    fact_check_table: str = "fact_check_vectors"
    occupation_code_table: str = "occupation_code_vectors"
    vector_dimension: int = 1024
    checkpoint_ttl_hours: int = 0
    checkpoint_ttl_interval: int = 1


@dataclass(frozen=True)
class ServiceConfig:
    """External service configuration."""

    mcp_server_url: str


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "console"  # 'json' or 'console'
    include_caller: bool = False
    disabled_loggers: list[str] | None = None
    noisy_loggers: list[str] | None = None
    clear_loggers: list[str] | None = None


@dataclass(frozen=True)
class LLMConfig:
    """LLM configuration."""

    orchestrator_temperature: float
    agent_temperature: float
    orchestrator_run_limit: int
    agent_run_limit: int


@dataclass(frozen=True)
class AppConfig:
    """Complete application configuration."""

    aws: AWSConfig
    azure: AzureConfig
    database: DatabaseConfig
    services: ServiceConfig
    logging: LoggingConfig
    llm: LLMConfig
    hyperscaler: str
    cors_allowed_origins: list[str]

    @classmethod
    def load(cls, env_file_path: Path | None = None) -> "AppConfig":
        """
        Load configuration from environment variables.

        Args:
            env_file_path: Optional path to .env file. If None, will look for .env
                          in the parent directory of this module.

        Returns:
            AppConfig: Fully loaded and validated configuration.

        Raises:
            AgentConfigurationError: If required environment variables are missing.
        """
        if env_file_path is None:
            env_file_path = Path(__file__).parent.parent / ".env"

        if env_file_path.exists():
            load_dotenv(dotenv_path=env_file_path)

        # Load and validate AWS configuration
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "eu-west-1")
        bedrock_model_id = os.getenv("BEDROCK_MODEL_ID")
        bedrock_embedding_model_id = os.getenv("BEDROCK_EMBEDDING_MODEL_ID")
        s3_bucket_name = os.getenv("S3_BUCKET_NAME")

        # Load Azure configuration
        azure_openai_model_endpoint = os.getenv("AZURE_OPENAI_MODEL_ENDPOINT")
        azure_openai_embedding_endpoint = os.getenv("AZURE_OPENAI_EMBEDDINGS_ENDPOINT") or azure_openai_model_endpoint
        azure_openai_key = os.getenv("AZURE_OPENAI_KEY")
        azure_embedding_deployment = os.getenv("AZURE_TEXT_EMBEDDING_DEPLOYMENT")
        azure_model_deployment = os.getenv("AZURE_MODEL_DEPLOYMENT")
        
        # Load Azure Speech API configuration (optional for voice features)
        azure_speech_api_key = os.getenv("AZURE_SPEECH_API_KEY")
        azure_speech_endpoint = os.getenv("AZURE_SPEECH_ENDPOINT") or azure_openai_model_endpoint
        azure_speech_tts_deployment = os.getenv("AZURE_SPEECH_TTS_DEPLOYMENT", "tts")
        azure_speech_stt_deployment = os.getenv("AZURE_SPEECH_STT_DEPLOYMENT", "gpt-4o-transcribe")

        # Determine hyperscaler selection
        hyperscaler = os.getenv("HYPER_SCALER", "AWS").strip().upper()
        valid_hyperscalers = {"AWS", "AZURE"}
        if hyperscaler not in valid_hyperscalers:
            raise AgentConfigurationError(f"Invalid HYPER_SCALER '{hyperscaler}'. Expected one of: {', '.join(sorted(valid_hyperscalers))}.")

        # Load and validate database configuration
        postgres_uri = os.getenv("POSTGRES_URI")
        document_table = os.getenv("DOCUMENT_TABLE_NAME", "document_vectors")
        checkpoint_ttl_hours = os.getenv("LANGGRAPH_CHECKPOINT_TTL_HOURS", 24)
        checkpoint_ttl_interval = os.getenv("LANGGRAPH_CHECKPOINT_TTL_CHECK_INTERVAL", 1)

        # Load and validate service configuration
        mcp_server_url = os.getenv("MCP_SERVER_URL")

        # Load temperatures
        orchestrator_temperature = float(os.getenv("ORCHESTRATOR_TEMPERATURE", "0.0"))
        agent_temperature = float(os.getenv("AGENT_TEMPERATURE", "0.3"))
        orchestrator_run_limit = int(os.getenv("ORCHESTRATOR_RUN_LIMIT", 5))
        agent_run_limit = int(os.getenv("AGENT_RUN_LIMIT", 5))

        # Load logging configuration
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "console").lower()
        log_include_caller = os.getenv("LOG_INCLUDE_CALLER", "false").lower() == "true"
        disabled_loggers_env = os.getenv("LOGGERS_DISABLED", "")
        disabled_loggers = [logger.strip() for logger in disabled_loggers_env.split(",") if logger.strip()] if disabled_loggers_env else None
        noisy_loggers_env = os.getenv("LOGGERS_NOISY", "")
        noisy_loggers = [logger.strip() for logger in noisy_loggers_env.split(",") if logger.strip()] if noisy_loggers_env else None
        clear_loggers_env = os.getenv("LOGGERS_CLEAR", "")
        clear_loggers = [logger.strip() for logger in clear_loggers_env.split(",") if logger.strip()] if clear_loggers_env else None

        cors_origins_env = os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
        cors_allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

        # Validate required variables
        missing_vars = []
        if not postgres_uri:
            missing_vars.append("POSTGRES_URI")
        if not mcp_server_url:
            missing_vars.append("MCP_SERVER_URL")
        if hyperscaler == "AWS":
            if not bedrock_model_id:
                missing_vars.append("BEDROCK_MODEL_ID")
            if not bedrock_embedding_model_id:
                missing_vars.append("BEDROCK_EMBEDDING_MODEL_ID")
        if hyperscaler == "AZURE":
            if not azure_openai_model_endpoint:
                missing_vars.append("AZURE_OPENAI_MODEL_ENDPOINT")
            if not azure_openai_embedding_endpoint:
                missing_vars.append("AZURE_OPENAI_EMBEDDINGS_ENDPOINT")
            if not azure_openai_key:
                missing_vars.append("AZURE_OPENAI_KEY")
            if not azure_embedding_deployment:
                missing_vars.append("AZURE_TEXT_EMBEDDING_DEPLOYMENT")
            if not azure_model_deployment:
                missing_vars.append("AZURE_MODEL_DEPLOYMENT")

        if missing_vars:
            raise AgentConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")

        assert postgres_uri is not None
        assert mcp_server_url is not None
        if hyperscaler == "AWS":
            assert bedrock_model_id is not None
            assert bedrock_embedding_model_id is not None
        if hyperscaler == "AZURE":
            assert azure_openai_model_endpoint is not None
            assert azure_openai_embedding_endpoint is not None
            assert azure_openai_key is not None
            assert azure_embedding_deployment is not None
            assert azure_model_deployment is not None
        return cls(
            aws=AWSConfig(
                access_key_id=aws_access_key_id,
                secret_access_key=aws_secret_access_key,
                region=aws_region,
                s3_bucket_name=s3_bucket_name,
                model_id=bedrock_model_id,
                embedding_model_id=bedrock_embedding_model_id,
            ),
            azure=AzureConfig(
                openai_model_endpoint=azure_openai_model_endpoint,
                openai_embedding_endpoint=azure_openai_embedding_endpoint,
                openai_key=azure_openai_key,
                text_embedding_deployment=azure_embedding_deployment,
                model_deployment=azure_model_deployment,
                speech_api_key=azure_speech_api_key,
                speech_endpoint=azure_speech_endpoint,
                speech_tts_deployment=azure_speech_tts_deployment,
                speech_stt_deployment=azure_speech_stt_deployment,
            ),
            database=DatabaseConfig(
                postgres_uri=postgres_uri,
                document_table=document_table,
                checkpoint_ttl_hours=checkpoint_ttl_hours,
                checkpoint_ttl_interval=checkpoint_ttl_interval,
            ),
            services=ServiceConfig(
                mcp_server_url=mcp_server_url,
            ),
            logging=LoggingConfig(
                level=log_level,
                format=log_format,
                include_caller=log_include_caller,
                disabled_loggers=disabled_loggers,
                noisy_loggers=noisy_loggers,
                clear_loggers=clear_loggers,
            ),
            llm=LLMConfig(
                orchestrator_temperature=orchestrator_temperature,
                agent_temperature=agent_temperature,
                orchestrator_run_limit=orchestrator_run_limit,
                agent_run_limit=agent_run_limit,
            ),
            hyperscaler=hyperscaler,
            cors_allowed_origins=cors_allowed_origins,
        )


# Singleton instance for application-wide access
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """
    Get the global application configuration.

    Returns:
        AppConfig: The loaded configuration instance.

    Raises:
        AgentConfigurationError: If configuration hasn't been loaded yet.
    """
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config
