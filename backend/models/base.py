from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for every JSON contract: unknown keys fail validation instead of vanishing."""
    model_config = ConfigDict(extra="forbid")
