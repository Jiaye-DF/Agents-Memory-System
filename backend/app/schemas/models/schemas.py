from pydantic import BaseModel


class LlmModelResponse(BaseModel):
    llm_model_uid: str
    provider: str
    model_id: str
    display_name: str
