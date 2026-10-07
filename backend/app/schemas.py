"""Request models. Responses are plain dicts built by the engine (see docs/API.md)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .config import DEFAULT_CONFIG, ZONES, RankingConfig


class ProfileIn(BaseModel):
    """A user profile. Skills may be plain strings or objects with a 'name'. Unknown skills are kept."""
    current_role: str | None = Field(None, max_length=200)
    department: str | None = Field(None, max_length=200)
    experience_years: float | None = Field(None, ge=0, le=60)
    skills: list[Any] = Field(default_factory=list, max_length=200)
    target_role: str | None = Field(None, max_length=200)
    target_company: str | None = Field(None, max_length=200)


class ConfigOverrides(BaseModel):
    zone_weights: dict[str, float] | None = None
    w_cosine: float | None = Field(None, ge=0, le=1)
    w_jaccard: float | None = Field(None, ge=0, le=1)
    use_zones: bool | None = None
    use_routing: bool | None = None
    routing_tau: float | None = Field(None, ge=0, le=1)
    diversity: bool | None = None
    diversity_epsilon: float | None = Field(None, ge=0, le=1)

    @field_validator("zone_weights")
    @classmethod
    def _zones(cls, v):
        if v is None:
            return v
        bad = [z for z in v if z not in ZONES]
        if bad:
            raise ValueError(f"unknown zone(s) {bad}; zones are {ZONES}")
        if any(w < 0 or w > 1 for w in v.values()):
            raise ValueError("zone weights must be between 0 and 1")
        return v

    def build(self) -> RankingConfig:
        cfg = DEFAULT_CONFIG.with_overrides(**self.model_dump(exclude_none=True))
        if cfg.use_zones and sum(cfg.zone_weights.values()) <= 0:
            raise ValueError("at least one zone weight must be positive")
        if cfg.w_cosine + cfg.w_jaccard <= 0:
            raise ValueError("at least one score weight must be positive")
        return cfg


Filters = dict[str, list[str]]


class SearchRequest(BaseModel):
    query: str = Field("", max_length=500)
    k: int = Field(10, ge=1, le=50)
    filters: Filters = Field(default_factory=dict)
    sort: Literal["best", "newest", "company", "location"] = "best"
    debug: bool = False
    profile: ProfileIn | None = None       # a CONFIRMED profile; used only for Career Fit, never for retrieval
    config: ConfigOverrides | None = None


class ExplainRequest(BaseModel):
    query: str = Field("", max_length=500)
    profile: ProfileIn | None = None


class CompareRequest(BaseModel):
    ids: list[int] = Field(..., min_length=2, max_length=4)
    profile: ProfileIn | None = None


class TransitionRequest(BaseModel):
    profile: ProfileIn
    target_role: str = Field(..., min_length=1, max_length=200)
    target_company: str | None = Field(None, max_length=200)
    k: int = Field(10, ge=1, le=30)


class TraceRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    k: int = Field(10, ge=1, le=30)
    filters: Filters = Field(default_factory=dict)
    config: ConfigOverrides | None = None
