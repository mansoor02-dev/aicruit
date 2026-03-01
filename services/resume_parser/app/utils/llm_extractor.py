import json
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import outlines
from outlines.integrations.transformers import JSONLogitsProcessor
from outlines.samplers import multinomial
from llm_extract_instruction import get_schema_description

MODEL_NAME = "microsoft/Phi-3.5-mini-instruct"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float32,
    device_map="cpu",
    trust_remote_code=True
)
# Wrap model for Outlines
generator = outlines.models.transformers(MODEL_NAME, device="cpu")

def extract_resume_with_llm(cleaned_text: str) -> dict:
    schema_desc = get_schema_description()
    
    prompt = f"""{schema_desc}

RESUME TEXT:
{cleaned_text}

Return ONLY the valid JSON (no markdown, no explanation):"""

    # Generate your exact JSON schema string from the description
    # Outlines needs the schema as a JSON string (we extract it from your docstring)
    json_schema_str = schema_desc.strip().split("```")[0].strip()

    # Use regex-free grammar: force model to follow your exact structure
    answer = outlines.generate.json(generator, json_schema_str)(
        prompt,
        max_tokens=2048,
        temperature=0.0,
        sampler=multinomial(top_p=0.95)
    )

    try:
        data = json.loads(answer)
        print("Success: Perfect JSON extracted")
        return data
    except json.JSONDecodeError:
        # This literally never happens with Outlines + json mode
        print("Warning: JSON failed (should not happen)")
        return {}