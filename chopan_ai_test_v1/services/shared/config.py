import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables with defaults"""
    return {
        "database": {
            "url": os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/chopan_ai"),
            "echo": False,
            "pool_size": 10,
            "max_overflow": 20
        },
        "redis": {
            "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            "decode_responses": True
        },
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", "4000")),
            "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
        },
        "aws": {
            "region": os.getenv("AWS_REGION", "us-east-1"),
            "s3_bucket": os.getenv("S3_BUCKET", "chopan-ai-snapshots"),
            "access_key_id": os.getenv("AWS_ACCESS_KEY_ID", ""),
            "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "")
        },
        "rate_limiting": {
            "requests_per_minute": int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60")),
            "retry_attempts": int(os.getenv("RATE_LIMIT_RETRY_ATTEMPTS", "3")),
            "backoff_factor": float(os.getenv("RATE_LIMIT_BACKOFF_FACTOR", "2.0"))
        },
        "snapshots": {
            "auto_snapshot": os.getenv("SNAPSHOTS_AUTO", "true").lower() == "true",
            "max_snapshots": int(os.getenv("SNAPSHOTS_MAX", "20")),
            "retention_days": int(os.getenv("SNAPSHOTS_RETENTION_DAYS", "90"))
        },
        "execution": {
            "max_execution_time": int(os.getenv("MAX_EXECUTION_TIME", "300")),
            "max_memory_mb": int(os.getenv("MAX_MEMORY_MB", "512")),
            "network_access": os.getenv("NETWORK_ACCESS", "true").lower() == "true",
            "max_file_size_mb": int(os.getenv("MAX_FILE_SIZE_MB", "20"))
        },
        "logging": {
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "format": os.getenv("LOG_FORMAT", "json"),
            "trace_id_header": os.getenv("TRACE_ID_HEADER", "X-Trace-ID")
        }
    }

def get_env_var(key: str, default: str = None) -> str:
    """Get environment variable with fallback to default"""
    value = os.getenv(key, default)
    if value and value.startswith("env:"):
        env_key = value[4:]
        value = os.getenv(env_key, default)
    return value

config = load_config()

OPENAI_API_KEY = get_env_var("OPENAI_API_KEY")
DATABASE_URL = get_env_var("DATABASE_URL", config["database"]["url"])
REDIS_URL = get_env_var("REDIS_URL", config["redis"]["url"])
AWS_REGION = get_env_var("AWS_REGION", config["aws"]["region"])
S3_BUCKET = get_env_var("S3_BUCKET", config["aws"]["s3_bucket"])