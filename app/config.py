from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    database_url: str = "sqlite:///./agent.db"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
