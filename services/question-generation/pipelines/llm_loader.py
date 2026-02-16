"""
LLM Loader - Initialize and manage local LLM models
"""
from pathlib import Path
from llama_cpp import Llama

MODEL_PATH = "models/Phi-3-mini-4k-instruct-q4.gguf"

class LLMLoader:
    """Manages local LLM initialization and configuration"""
    
    def __init__(
        self,
        model_path: str = MODEL_PATH,
        n_ctx: int = 2048,
        n_threads: int = 4,
        n_batch: int = 512
    ):
        self.model_path = Path(model_path)
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.n_batch = n_batch
        self.llm = None
    
    def load(self) -> Llama:
        """Load LLM model"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        print(f"🤖 Loading LLM from {self.model_path.name}...")
        print(f"   Context: {self.n_ctx}, Threads: {self.n_threads}")
        
        self.llm = Llama(
            model_path=str(self.model_path),
            n_ctx=self.n_ctx,
            n_threads=self.n_threads,
            n_batch=self.n_batch,
            use_mlock=True,  # Lock in memory for faster access
            verbose=False
        )
        
        print(f"✓ LLM loaded successfully")
        return self.llm
    
    def get_llm(self) -> Llama:
        """Get loaded LLM instance"""
        if self.llm is None:
            return self.load()
        return self.llm