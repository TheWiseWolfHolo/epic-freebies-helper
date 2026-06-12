# -*- coding: utf-8 -*-
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from hcaptcha_challenger.agent import AgentConfig
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict

from extensions.llm_adapter import apply_llm_patch

# --- 核心路径定义 ---
PROJECT_ROOT = Path(__file__).parent
VOLUMES_DIR = PROJECT_ROOT.joinpath("volumes")
LOG_DIR = VOLUMES_DIR.joinpath("logs")
USER_DATA_DIR = VOLUMES_DIR.joinpath("user_data")
RUNTIME_DIR = VOLUMES_DIR.joinpath("runtime")
SCREENSHOTS_DIR = VOLUMES_DIR.joinpath("screenshots")
RECORD_DIR = VOLUMES_DIR.joinpath("record")
HCAPTCHA_DIR = VOLUMES_DIR.joinpath("hcaptcha")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _coerce_secret_input(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    value = str(value).strip()
    return value or None


# === 配置类定义 ===
class EpicSettings(AgentConfig):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    GEMINI_API_KEY: SecretStr | None = Field(default=None, description="Gemini/AiHubMix API key")

    GEMINI_BASE_URL: str = Field(
        default="", description="Optional Gemini-compatible base URL override"
    )

    GEMINI_MODEL: str = Field(default="gemini-2.5-pro", description="Gemini default model")

    LLM_PROVIDER: str = Field(default="", description="Supported values: gemini, glm, openai")

    GLM_API_KEY: SecretStr | None = Field(default=None, description="GLM API key")

    GLM_BASE_URL: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4", description="GLM OpenAI-compatible base URL"
    )

    GLM_MODEL: str = Field(default="glm-4.5v", description="GLM vision-capable default model")

    OPENAI_API_KEY: SecretStr | None = Field(
        default=None, description="OpenAI-compatible relay API key"
    )

    OPENAI_BASE_URL: str = Field(
        default="", description="OpenAI-compatible relay base URL, usually ending in /v1"
    )

    OPENAI_MODEL: str = Field(default="gpt-4o", description="OpenAI-compatible vision model")

    BROWSER_BACKEND: str = Field(
        default="auto", description="Supported values: auto, camoufox, playwright"
    )

    EPIC_EMAIL: str = Field(default_factory=lambda: _env("EPIC_EMAIL"))
    EPIC_PASSWORD: SecretStr = Field(default_factory=lambda: _env("EPIC_PASSWORD"))
    DISABLE_BEZIER_TRAJECTORY: bool = Field(default=False)
    WAIT_FOR_CHALLENGE_VIEW_TO_RENDER_MS: int = Field(default=3000)

    CHALLENGE_CLASSIFIER_MODEL: str = Field(default="")
    IMAGE_CLASSIFIER_MODEL: str = Field(default="")
    SPATIAL_POINT_REASONER_MODEL: str = Field(default="")
    SPATIAL_PATH_REASONER_MODEL: str = Field(default="")

    cache_dir: Path = HCAPTCHA_DIR.joinpath(".cache")
    challenge_dir: Path = HCAPTCHA_DIR.joinpath(".challenge")
    captcha_response_dir: Path = HCAPTCHA_DIR.joinpath(".captcha")

    ENABLE_APSCHEDULER: bool = Field(default=True)
    TASK_TIMEOUT_SECONDS: int = Field(default=900)
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    CELERY_WORKER_CONCURRENCY: int = Field(default=1)
    CELERY_TASK_TIME_LIMIT: int = Field(default=1200)
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=900)

    @model_validator(mode="before")
    @classmethod
    def _bridge_provider_credentials(cls, raw_data):
        data = dict(raw_data) if isinstance(raw_data, dict) else {}

        provider = str(data.get("LLM_PROVIDER") or "").strip().lower()
        glm_key = _coerce_secret_input(data.get("GLM_API_KEY"))
        gemini_key = _coerce_secret_input(data.get("GEMINI_API_KEY"))
        openai_key = _coerce_secret_input(data.get("OPENAI_API_KEY"))

        if provider not in {"gemini", "glm", "openai"}:
            data["LLM_PROVIDER"] = "openai" if openai_key else "glm" if glm_key else "gemini"

        # `hcaptcha-challenger` still expects GEMINI_API_KEY in its base settings model.
        # Seed it before field validation so non-Gemini environments work in local runs and CI.
        if gemini_key is None and (glm_key is not None or openai_key is not None):
            data["GEMINI_API_KEY"] = openai_key or glm_key

        return data

    @model_validator(mode="after")
    def _apply_runtime_defaults(self):
        for field_name in (
            "GEMINI_BASE_URL",
            "GEMINI_MODEL",
            "LLM_PROVIDER",
            "GLM_BASE_URL",
            "GLM_MODEL",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "BROWSER_BACKEND",
            "EPIC_EMAIL",
            "CHALLENGE_CLASSIFIER_MODEL",
            "IMAGE_CLASSIFIER_MODEL",
            "SPATIAL_POINT_REASONER_MODEL",
            "SPATIAL_PATH_REASONER_MODEL",
        ):
            value = getattr(self, field_name, None)
            if isinstance(value, str):
                setattr(self, field_name, value.strip())

        provider = (self.LLM_PROVIDER or "").strip().lower()
        if provider not in {"gemini", "glm", "openai"}:
            provider = "openai" if self.OPENAI_API_KEY else "glm" if self.GLM_API_KEY else "gemini"
        self.LLM_PROVIDER = provider

        if self.GEMINI_API_KEY is None and (
            self.OPENAI_API_KEY is not None or self.GLM_API_KEY is not None
        ):
            self.GEMINI_API_KEY = self.OPENAI_API_KEY or self.GLM_API_KEY

        provider_default = {
            "glm": self.GLM_MODEL,
            "openai": self.OPENAI_MODEL,
        }.get(provider, self.GEMINI_MODEL)
        if not self.CHALLENGE_CLASSIFIER_MODEL:
            self.CHALLENGE_CLASSIFIER_MODEL = provider_default
        if not self.IMAGE_CLASSIFIER_MODEL:
            self.IMAGE_CLASSIFIER_MODEL = provider_default
        if not self.SPATIAL_POINT_REASONER_MODEL:
            self.SPATIAL_POINT_REASONER_MODEL = provider_default
        if not self.SPATIAL_PATH_REASONER_MODEL:
            self.SPATIAL_PATH_REASONER_MODEL = provider_default

        browser_backend = (self.BROWSER_BACKEND or "").strip().lower()
        self.BROWSER_BACKEND = browser_backend or "auto"

        return self

    @property
    def user_data_dir(self) -> Path:
        target_ = self.user_data_dir_for("camoufox")
        return target_

    def user_data_dir_for(self, backend: str) -> Path:
        backend = (backend or "camoufox").strip().lower()
        suffix = f".{backend}"
        target_ = USER_DATA_DIR.joinpath(f"{self.EPIC_EMAIL}{suffix}")
        target_.mkdir(parents=True, exist_ok=True)
        return target_

    @property
    def llm_configuration_error(self) -> str | None:
        provider = (self.LLM_PROVIDER or "").strip().lower()

        if provider == "glm" and self.GLM_API_KEY is None:
            return (
                "Invalid LLM configuration: LLM_PROVIDER=glm but GLM_API_KEY is empty. "
                "Set GLM_API_KEY in GitHub Actions Secrets, or switch LLM_PROVIDER to gemini "
                "if you intend to use Gemini/AiHubMix."
            )

        if provider == "gemini" and self.GEMINI_API_KEY is None:
            return (
                "Invalid LLM configuration: LLM_PROVIDER=gemini but GEMINI_API_KEY is empty. "
                "Set GEMINI_API_KEY in GitHub Actions Secrets, or switch LLM_PROVIDER to glm "
                "if you intend to use GLM."
            )

        if provider == "openai":
            if self.OPENAI_API_KEY is None:
                return (
                    "Invalid LLM configuration: LLM_PROVIDER=openai but OPENAI_API_KEY is empty. "
                    "Set OPENAI_API_KEY in GitHub Actions Secrets, or switch LLM_PROVIDER."
                )
            if not self.OPENAI_BASE_URL:
                return (
                    "Invalid LLM configuration: LLM_PROVIDER=openai but OPENAI_BASE_URL is empty. "
                    "Set the OpenAI-compatible relay base URL in GitHub Actions Secrets."
                )

        return None


settings = EpicSettings()
settings.ignore_request_questions = ["Please drag the crossing to complete the lines"]
apply_llm_patch(settings)
