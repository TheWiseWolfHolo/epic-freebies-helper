# -*- coding: utf-8 -*-
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from hcaptcha_challenger.agent import AgentConfig
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict

from extensions.hcaptcha_adapter import apply_hcaptcha_drag_patch
from llm.urls import LLMProvider, normalize_base_url

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

    # hcaptcha-challenger still constructs its default Gemini provider before our
    # provider-neutral adapter is injected. Keep the required inherited field
    # internal and exclude it from dumps; no request uses this sentinel.
    GEMINI_API_KEY: SecretStr = Field(
        default=SecretStr("__provider_managed__"),
        exclude=True,
        repr=False,
        description="Internal compatibility sentinel",
    )
    LLM_PROVIDER: str = Field(
        default=LLMProvider.OPENAI.value,
        description="Supported values: openai, openai-responses, gemini, claude",
    )
    LLM_API_KEY: SecretStr | None = Field(default=None, description="LLM API key")
    LLM_BASE_URL: str = Field(default="", description="Optional provider API root override")
    LLM_MODEL: str = Field(default="", description="Vision-capable model name")

    BROWSER_BACKEND: str = Field(
        default="auto", description="Supported values: auto, camoufox, playwright"
    )

    EPIC_EMAIL: str = Field(default_factory=lambda: _env("EPIC_EMAIL"))
    EPIC_PASSWORD: SecretStr = Field(default_factory=lambda: _env("EPIC_PASSWORD"))
    DISABLE_BEZIER_TRAJECTORY: bool = Field(default=False)
    RETRY_ON_FAILURE: bool = Field(
        default=False,
        description="Disable recursive hCaptcha retries; application flows own retry limits.",
    )
    WAIT_FOR_CHALLENGE_VIEW_TO_RENDER_MS: int = Field(default=3000)

    CHALLENGE_CLASSIFIER_MODEL: str = Field(default="", exclude=True)
    IMAGE_CLASSIFIER_MODEL: str = Field(default="", exclude=True)
    SPATIAL_POINT_REASONER_MODEL: str = Field(default="", exclude=True)
    SPATIAL_PATH_REASONER_MODEL: str = Field(default="", exclude=True)

    cache_dir: Path = HCAPTCHA_DIR.joinpath(".cache")
    challenge_dir: Path = HCAPTCHA_DIR.joinpath(".challenge")
    captcha_response_dir: Path = HCAPTCHA_DIR.joinpath(".captcha")

    ENABLE_APSCHEDULER: bool = Field(default=True)
    TASK_TIMEOUT_SECONDS: int = Field(default=900)
    AUTH_MAX_ATTEMPTS: int = Field(default=5, ge=3, le=8)
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    CELERY_WORKER_CONCURRENCY: int = Field(default=1)
    CELERY_TASK_TIME_LIMIT: int = Field(default=1200)
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=900)

    @model_validator(mode="before")
    @classmethod
    def _prepare_provider_settings(cls, raw_data):
        data = dict(raw_data) if isinstance(raw_data, dict) else {}
        provider = str(data.get("LLM_PROVIDER") or LLMProvider.OPENAI.value).strip().lower()
        data["LLM_PROVIDER"] = provider

        # AgentConfig currently validates a Gemini-named field before AgentV lets us inject
        # its provider-neutral ChatProvider. Keep this dependency shim internal; requests
        # use only LLM_API_KEY through app.llm.
        llm_key = _coerce_secret_input(data.get("LLM_API_KEY"))
        data["GEMINI_API_KEY"] = llm_key or "__provider_managed__"

        return data

    @model_validator(mode="after")
    def _apply_runtime_defaults(self):
        for field_name in (
            "LLM_PROVIDER",
            "LLM_BASE_URL",
            "LLM_MODEL",
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

        provider = LLMProvider((self.LLM_PROVIDER or "").strip().lower())
        self.LLM_PROVIDER = provider.value
        if self.LLM_BASE_URL:
            self.LLM_BASE_URL = normalize_base_url(provider, self.LLM_BASE_URL)

        for field_name in (
            "CHALLENGE_CLASSIFIER_MODEL",
            "IMAGE_CLASSIFIER_MODEL",
            "SPATIAL_POINT_REASONER_MODEL",
            "SPATIAL_PATH_REASONER_MODEL",
        ):
            setattr(self, field_name, self.LLM_MODEL)

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
        if self.LLM_API_KEY is None:
            return "Invalid LLM configuration: LLM_API_KEY is empty."
        if not self.LLM_MODEL:
            return "Invalid LLM configuration: LLM_MODEL is empty."

        return None


settings = EpicSettings()
settings.ignore_request_questions = ["Please drag the crossing to complete the lines"]
apply_hcaptcha_drag_patch()
