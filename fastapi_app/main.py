
from fastapi import FastAPI
from pydantic import BaseModel

# Import your existing categorization function
from ai_tools.utils import categorization

app = FastAPI()

class TextIn(BaseModel):
    text: str

class CategorizationOut(BaseModel):
    topics: list

@app.post("/categorize", response_model=CategorizationOut)
def categorize_text(payload: TextIn):
    predictions = categorization([payload.text])
    return {"topics": predictions}
