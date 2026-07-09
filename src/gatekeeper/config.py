from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper"
    log_level: str = "INFO"
    policy_path: str = "policies/policy_registry.yaml"
    engine_backend: str = "pydantic"  # "pydantic" or "opa"
    opa_url: str = "http://localhost:8181"


settings = Settings()
