from pydantic import BaseModel, Field


class ProviderStatusResponse(BaseModel):
    name: str
    display_name: str
    is_enabled: bool
    status: str
    supports_latest_price: bool
    supports_daily_history: bool


class ProvidersStatusResponse(BaseModel):
    providers: list[ProviderStatusResponse]


class RefreshRequest(BaseModel):
    symbols: list[str]
    data_types: list[str] = Field(default_factory=lambda: ["latest_price", "daily_history"])
    start_date: str | None = None
    end_date: str | None = None
    priority: str = "normal"


class RefreshResponse(BaseModel):
    job_id: str
    status: str = "queued"
    symbols_queued: list[str] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    provider: str | None = None
    symbol: str | None = None
    error_message: str | None = None


class SymbolSearchResult(BaseModel):
    symbol: str
    name: str | None = None
    exchange: str | None = None
    asset_type: str | None = None
    currency: str | None = None
    country: str | None = None


class SymbolSearchResponse(BaseModel):
    results: list[SymbolSearchResult]


class SymbolMetadataResponse(BaseModel):
    symbol: str
    name: str | None = None
    exchange: str | None = None
    asset_type: str | None = None
    currency: str | None = None
    country: str | None = None
    sector: str | None = None
    industry: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "market-data-api"
    version: str = "0.1.0"
