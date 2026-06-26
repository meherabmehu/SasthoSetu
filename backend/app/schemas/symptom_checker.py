from pydantic import BaseModel


class SymptomRequest(BaseModel):
    symptoms: str


class SymptomResponse(BaseModel):
    severity: str
    possible_disease: str
    recommended_specialist: str
    recommendation: str