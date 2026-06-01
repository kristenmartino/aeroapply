"""Typed configuration: environment (.env) + operator profile (config/profile.yaml).

Two layers:
  * Settings — secrets & runtime knobs from the environment / .env (BaseSettings).
  * Profile  — the operator's filters, bouncer rules, ranking weights, and autonomy
               gates from config/profile.yaml (validated Pydantic models).

`get_settings()` and `get_profile()` are cached. `profile.to_bouncer_config()` hands
the SourcingBouncer its rules, so sourcing is fully config-driven. The ranking weights
and autonomy thresholds exposed here are the knobs the calibration plan tunes
(see docs/CALIBRATION.md).
"""

from __future__ import annotations

import functools
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from aeroapply.sourcing.bouncer import BouncerConfig


class Settings(BaseSettings):
    """Secrets and runtime knobs from the environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql://aeroapply:aeroapply@localhost:5432/aeroapply"

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    ollama_host: str = "http://localhost:11434"

    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    default_mode: str = "review"
    wip_limit: int = 5
    scheduler_cycle_minutes: int = 180
    min_ats_score: float = 0.90
    min_agent_confidence: float = 0.95

    profile_path: str = "config/profile.yaml"


# --- config/profile.yaml models ------------------------------------------
class Home(BaseModel):
    label: str = ""
    lat: float
    lon: float


class Operator(BaseModel):
    name: str
    primary_email: str = ""
    agent_email: str = ""
    headline: str = ""
    work_auth: str = ""
    home: Home


class SearchProfileCfg(BaseModel):
    name: str = "default"
    locations: list[str] = Field(default_factory=list)
    distance_miles: int = 40
    remote_modes: list[str] = Field(default_factory=lambda: ["remote", "hybrid"])
    languages: list[str] = Field(default_factory=lambda: ["English"])
    salary_floor: int = 0
    currency: str = "USD"
    include_linkedin: bool = True
    exclude_companies: list[str] = Field(default_factory=list)


class TargetRole(BaseModel):
    title: str
    alignment: float = 1.0


class BouncerCfg(BaseModel):
    max_commute_miles: float = 40.0
    min_salary_floor: int = 0
    max_age_days: int = 45
    drop_title_regex: str
    legal_blocker_regex: str


class RankingWeights(BaseModel):
    """execution_priority weights (the manual_override trump is separate)."""

    title: float
    location: float
    recency: float
    competition: float
    urgency: float

    @model_validator(mode="after")
    def _must_sum_to_one(self) -> RankingWeights:
        total = self.title + self.location + self.recency + self.competition + self.urgency
        if abs(total - 1.0) > 1e-3:
            raise ValueError(f"ranking weights must sum to 1.0 (got {total:.3f})")
        return self


class SchedulerCfg(BaseModel):
    wip_limit: int = 5
    cycle_minutes: int = 180


class AutonomyCfg(BaseModel):
    default_mode: str = "review"
    auto_submit_sources: list[str] | None = None  # None = no allowlist; [] = block all
    always_human_sources: list[str] = Field(default_factory=list)
    min_ats_score: float = 0.90
    min_agent_confidence: float = 0.95


class Profile(BaseModel):
    operator: Operator
    search_profile: SearchProfileCfg
    target_roles: list[TargetRole] = Field(default_factory=list)
    bouncer: BouncerCfg
    ranking_weights: RankingWeights
    scheduler: SchedulerCfg = Field(default_factory=SchedulerCfg)
    autonomy: AutonomyCfg = Field(default_factory=AutonomyCfg)

    def to_bouncer_config(self) -> BouncerConfig:
        """Build the dataclass the SourcingBouncer consumes."""
        return BouncerConfig(
            home_coords=(self.operator.home.lat, self.operator.home.lon),
            max_commute_miles=self.bouncer.max_commute_miles,
            min_salary_floor=self.bouncer.min_salary_floor,
            max_age_days=self.bouncer.max_age_days,
            drop_title_regex=self.bouncer.drop_title_regex,
            legal_blocker_regex=self.bouncer.legal_blocker_regex,
        )


def load_profile(path: str | Path) -> Profile:
    data = yaml.safe_load(Path(path).read_text())
    return Profile.model_validate(data)


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()


@functools.lru_cache
def get_profile() -> Profile:
    return load_profile(get_settings().profile_path)


__all__ = ["Settings", "Profile", "load_profile", "get_settings", "get_profile"]
