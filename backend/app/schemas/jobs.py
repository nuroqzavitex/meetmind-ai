from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    meeting_id: str
    status: str
    step: str | None
    progress: float
    error: str | None
