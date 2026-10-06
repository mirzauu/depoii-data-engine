from pathlib import Path
from typing import Optional, Dict, Any, Literal
import yaml
from pydantic import BaseModel, Field


class SocrataConfig(BaseModel):
    domain: str
    dataset_id: str
    resource_name: Optional[str] = "Building Permits"
    date_field: Optional[str] = "issue_date"
    description_field: Optional[str] = "description"
    valuation_field: Optional[str] = "estimated_cost"
    contractor_field: Optional[str] = "contractor_name"
    address_field: Optional[str] = "street_address"


class PortalConfig(BaseModel):
    base_url: str
    search_path: str = "/Cap/CapHome.aspx"
    module: str = "Building"
    sub_type: Optional[str] = "Commercial"


class DisclaimerConfig(BaseModel):
    has_disclaimer: bool = False
    checkbox_selector: Optional[str] = None
    continue_button: Optional[str] = None


class SearchFormConfig(BaseModel):
    date_start_selector: str
    date_end_selector: str
    keyword_selector: Optional[str] = None
    search_button: str
    date_format: str = "MM/DD/YYYY"


class ResultsConfig(BaseModel):
    table_selector: str
    pagination_style: Literal["link_next", "infinite_scroll", "load_more_button"] = "link_next"
    next_page_selector: Optional[str] = None
    max_pages: int = 20


class ColumnMappingConfig(BaseModel):
    permit_number: int = 1
    record_type: int = 2
    address: int = 3
    issue_date: int = 4
    status: int = 5
    description: Optional[int] = None


class AntiBotConfig(BaseModel):
    has_captcha: bool = False
    has_cloudflare: bool = False
    request_delay_ms: int = 2000
    max_retries: int = 3


class RateLimitConfig(BaseModel):
    requests_per_minute: int = 10
    concurrent_sessions: int = 1
    batch_size: int = 1000


class CityConfig(BaseModel):
    jurisdiction: str
    state: str
    county: Optional[str] = None
    platform: Literal["socrata", "accela", "energov", "custom_html"]
    accela_version: Optional[str] = None

    socrata: Optional[SocrataConfig] = None
    portal: Optional[PortalConfig] = None
    disclaimer: Optional[DisclaimerConfig] = None
    search_form: Optional[SearchFormConfig] = None
    results: Optional[ResultsConfig] = None
    columns: Optional[ColumnMappingConfig] = None
    anti_bot: Optional[AntiBotConfig] = None
    rate_limit: Optional[RateLimitConfig] = None


def get_city_config_path(city_key: str, base_dir: Optional[Path] = None) -> Path:
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / "city_configs"
    return base_dir / f"{city_key}.yaml"


def load_city_config(city_key: str, base_dir: Optional[Path] = None) -> CityConfig:
    path = get_city_config_path(city_key, base_dir)
    if not path.exists():
        raise FileNotFoundError(f"City configuration not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return CityConfig.model_validate(data)


def list_configured_cities(base_dir: Optional[Path] = None) -> list[str]:
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent / "city_configs"
    if not base_dir.exists():
        return []
    return [
        p.stem for p in base_dir.glob("*.yaml")
        if not p.name.startswith("_")
    ]
