def run_score_inference(system_prompt: str, user_payload: str) -> dict:
    """Call Gemini with a custom system prompt and JSON-mode user payload.

    Returns the parsed JSON dict. Raises on transport / JSON errors.
    """
    import json as _json
    import os

    from dotenv import load_dotenv
    from google import genai

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=user_payload,
        config={
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )
    return _json.loads(response.text)