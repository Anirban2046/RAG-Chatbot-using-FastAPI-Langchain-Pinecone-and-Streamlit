from pydantic import BaseModel, Field


class AnonymousSessionStatePayload(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)
    uploaded_docs: list[str] = Field(default_factory=list)


class AnonymousClosePayload(BaseModel):
    client_id: str | None = None
