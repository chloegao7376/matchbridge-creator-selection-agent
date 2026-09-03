from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RetrievalAdvancedConfig(BaseModel):
    keyword_weight: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="关键词召回在混合排名中的相对权重。",
    )
    vector_weight: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="内容相似度召回在混合排名中的相对权重。",
    )
    retrieval_depth: int = Field(
        default=100,
        ge=1,
        le=200,
        description="关键词和内容相似度每一路最多召回的候选人数。",
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="RRF排名平滑参数；值越小越强调单路头部排名，建议保持默认60。",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        if self.keyword_weight + self.vector_weight <= 0:
            raise ValueError("keyword_weight and vector_weight cannot both be zero")
        return self


class FitDimensionWeights(BaseModel):
    content_relevance: float = Field(ge=0, le=1, examples=[0.30], description="内容相关性权重。")
    audience_fit: float = Field(ge=0, le=1, examples=[0.20], description="受众适配度权重。")
    performance: float = Field(ge=0, le=1, examples=[0.15], description="历史效果权重。")
    cost_efficiency: float = Field(ge=0, le=1, examples=[0.10], description="成本效率权重。")
    traffic_quality: float = Field(ge=0, le=1, examples=[0.10], description="流量质量权重。")
    delivery_reliability: float = Field(ge=0, le=1, examples=[0.10], description="履约能力权重。")
    data_quality: float = Field(ge=0, le=1, examples=[0.05], description="数据质量权重。")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        total = sum(self.model_dump().values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"fit dimension weights must sum to 1.0; received {total:.6f}")
        return self


class FitConfig(BaseModel):
    mode: Literal["default", "custom"] = Field(
        default="default",
        description="default使用系统权重；custom开放完整七维权重。",
    )
    weights: FitDimensionWeights | None = Field(
        default=None,
        description="仅mode=custom时必填，七维权重合计必须为1。",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        if self.mode == "custom" and self.weights is None:
            raise ValueError("weights are required when fit mode is custom")
        if self.mode == "default" and self.weights is not None:
            raise ValueError("weights must be omitted when fit mode is default")
        return self


class RecommendationRunRequest(BaseModel):
    campaign_id: str = Field(
        min_length=1,
        max_length=32,
        description="本次选号使用的Campaign Brief ID。",
    )
    query: str = Field(
        min_length=1,
        max_length=200,
        description="本次选号希望重点匹配的内容方向。",
    )
    candidate_count: int = Field(
        default=50,
        ge=1,
        le=200,
        description="最多进入Fit特征精算和最终排序的候选人数。",
    )
    retrieval_advanced: RetrievalAdvancedConfig = Field(
        default_factory=RetrievalAdvancedConfig,
        description="折叠的召回高级设置。",
    )
    fit: FitConfig = Field(
        default_factory=FitConfig,
        description="Fit特征评分设置：系统默认或自定义七维权重。",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_candidate_pool(self) -> Self:
        if self.retrieval_advanced.retrieval_depth < self.candidate_count:
            raise ValueError("retrieval_depth must be greater than or equal to candidate_count")
        return self


class FitRunRequest(BaseModel):
    campaign_id: str = Field(
        min_length=1,
        max_length=32,
        description="需要计算适配度的Campaign Brief ID。",
    )
    query: str = Field(
        min_length=1,
        max_length=200,
        description="已用于候选召回的内容匹配重点。",
    )
    candidate_count: int = Field(
        default=50,
        ge=1,
        le=200,
        description="进入七维Fit计算的候选人数。",
    )
    fit: FitConfig = Field(
        default_factory=FitConfig,
        description="默认使用30/20/15/10/10/10/5；仅custom模式开放七维权重。",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "campaign_id": "cmp_0001",
                    "query": "配料表",
                    "candidate_count": 50,
                    "fit": {"mode": "default"},
                },
                {
                    "campaign_id": "cmp_0001",
                    "query": "配料表",
                    "candidate_count": 50,
                    "fit": {
                        "mode": "custom",
                        "weights": {
                            "content_relevance": 0.30,
                            "audience_fit": 0.20,
                            "performance": 0.15,
                            "cost_efficiency": 0.10,
                            "traffic_quality": 0.10,
                            "delivery_reliability": 0.10,
                            "data_quality": 0.05,
                        },
                    },
                },
            ]
        },
    )


class HistoricalAvailabilityRunRequest(BaseModel):
    campaign_id: str = Field(
        min_length=1,
        max_length=32,
        description="需要由historical-data-availability-checker检测的Campaign Brief ID。",
    )
    query: str = Field(
        min_length=1,
        max_length=200,
        description="用于Hybrid召回候选池的内容匹配重点。",
    )
    candidate_count: int = Field(
        default=50,
        ge=1,
        le=200,
        description="进入历史数据可用性检测的Hybrid候选人数。",
    )
    retrieval_advanced: RetrievalAdvancedConfig = Field(
        default_factory=RetrievalAdvancedConfig,
        description="折叠的Hybrid召回高级设置。",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_candidate_pool(self) -> Self:
        if self.retrieval_advanced.retrieval_depth < self.candidate_count:
            raise ValueError("retrieval_depth must be greater than or equal to candidate_count")
        return self
