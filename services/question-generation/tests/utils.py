# tests/utils.py
import os
from pathlib import Path
from llama_cpp import Llama

def get_test_llm():
    """
    Returns a real LLM if model exists, otherwise returns a smart MockLLM
    Used only in __main__ test blocks
    """
    model_path = Path("models/llm/Phi-3-mini-4k-instruct-q4.gguf")
    
    if model_path.exists():
        print(f"Real LLM found! Using {model_path.name} for testing")
        return Llama(
            model_path=str(model_path),
            n_ctx=2048,
            n_threads=4,
            n_batch=512,
            verbose=False
        )
    else:
        print("Model not found → using MockLLM (safe fallback)")
        class MockLLM:
            def create_chat_completion(self, **kwargs):
                # Smart mock: returns realistic JSON
                score = 0.75
                feedback = "Mock response - real model not found"
                return {
                    "choices": [{
                        "message": {
                            "content": f'{{"score": {score}, "confidence": 0.8, "feedback": "{feedback}"}}'
                        }
                    }]
                }
        return MockLLM()