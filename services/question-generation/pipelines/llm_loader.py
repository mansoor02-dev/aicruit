import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class OpenRouterChat:
    """Wrapper for OpenRouter API"""
    def __init__(
        self,
        model_name: str = "deepseek/deepseek-r1-0528:free",
        site_url: str | None = None,
        site_name: str | None = None,
    ):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        self.model_name = model_name
        self.site_url = site_url
        self.site_name = site_name

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 512,
        top_p: float = 0.95,
        extra_body: Dict[str, Any] | None = None,
        **_,
    ) -> Dict[str, Any]:

        extra_headers = {}
        if self.site_url:
            extra_headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            extra_headers["X-Title"] = self.site_name

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            extra_headers=extra_headers or None,
            extra_body=extra_body or {},
        )
        choices = response.choices or []
        msg = choices[0].message if choices else None
        content = msg.content.strip() if msg and msg.content else ""        
        
        return {
            "choices": [
                {
                    "message": {
                        "role": msg.role if msg else "assistant",
                        "content": content
                    }
                }
            ]
        }


class GeminiChat:
    """Wrapper for Google Gemini API using new google-genai package"""
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError(
                "google-genai package not installed. "
                "Install with: pip install google-genai"
            )

        self.model_name = model_name
        
    def _flatten_messages(self, messages: List[Dict[str, str]]) -> str:
        return "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in messages
        )

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 512,
        **_
    ) -> Dict[str, Any]:

        prompt = self._flatten_messages(messages)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "top_p": 0.95,
            },
        )
        text = response.text if hasattr(response, "text") else ""
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": text.strip()
                    }
                }
            ]
        }


class LLMLoader:
    """Loads OpenRouter or Gemini model with unified interface"""
    def __init__(
        self,
        model_type: str = "gemini"
    ):
        self.model_type = model_type
        self._llm: Optional[Any] = None

    def load(self):
        if self._llm is not None:
            return self._llm
        elif self.model_type == "openrouter":
            self._llm = OpenRouterChat().create_chat_completion
        else: 
            self._llm = GeminiChat().create_chat_completion
        return self._llm

    def get_llm(self):
        return self.load()