from fastapi import APIRouter
import torch
from ...core import bert_models


router = APIRouter(prefix="/bert", tags=["BERT"])

@router.post("/analyze/")
async def analyze_text(text: str, model_type: str = "biobert"):
    """
    Analyze medical text using BioBERT or ClinicalBERT.
    Example POST:
    {
      "text": "Patient shows signs of hypertension.",
      "model_type": "clinibert"
    }
    """
    if model_type == "clinibert":
        tokenizer = bert_models.clinibert_tokenizer
        model = bert_models.clinibert_model
    else:
        tokenizer = bert_models.biobert_tokenizer
        model = bert_models.biobert_model

    inputs = tokenizer(text, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)

    return {
        "model": model_type,
        "raw_output": outputs.logits.tolist()
    }

