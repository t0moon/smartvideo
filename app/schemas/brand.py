from pydantic import BaseModel, Field


class BrandProfile(BaseModel):
    brand_name: str = ""
    product_name: str = ""
    product_category: str = ""
    product_description: str = ""
    target_audience: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    core_selling_points: list[str] = Field(default_factory=list)
    usage_scenarios: list[str] = Field(default_factory=list)
    brand_tone: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    trust_signals: list[str] = Field(default_factory=list)
    taboo_points: list[str] = Field(default_factory=list)
    ad_angles: list[str] = Field(default_factory=list)
    uncertain_fields: list[str] = Field(default_factory=list)
