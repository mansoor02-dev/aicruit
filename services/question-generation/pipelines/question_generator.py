"""
Question Generator - Creates both new topic questions and follow-ups

Handles two distinct modes:
1. NEW TOPIC: Pick from dataset, use retrieval for context
2. FOLLOW-UP: Generate based on previous Q&A, use LLM creativity
"""
import random
import re
from typing import List, Dict, Optional, Tuple
from llama_cpp import Llama
from tests.utils import get_test_llm
import json



class QuestionGenerator:
    """
    Generates interview questions using hybrid approach:
    - New topics: Dataset-based with RAG context
    - Follow-ups: LLM-generated based on conversation
    """
    
    def __init__(
        self,
        llm: Llama,
        dataset_questions: List[Dict],  # From CSV
        candidate_resume: str = "",    
        job_description: str = "",
        retriever=None  # FAISS retriever (optional)
    ):
        self.llm = llm
        self.dataset = dataset_questions
        self.candidate_resume = candidate_resume      
        self.job_description = job_description
        self.retriever = retriever
        
        # Cache used questions to avoid repetition
        self.used_question_ids = set()
    
    def generate_new_topic_question(
        self,
        topics_covered: List[str],
        difficulty: str = "medium"
    ) -> Tuple[str, Dict]:
        """
        Generate a NEW TOPIC question (not a follow-up)
        
        Strategy:
        1. Filter dataset by difficulty
        2. Avoid recently covered topics
        3. Pick a question from dataset
        4. Optionally: Use LLM to rephrase for variety
        
        Returns:
            (question_text, metadata)
        """
        
        # Filter by difficulty
        candidates = [
            q for q in self.dataset 
            if q["difficulty"].lower() == difficulty.lower()
            and q["id"] not in self.used_question_ids
        ]
        
        # If not enough questions, allow reuse
        if len(candidates) < 3:
            candidates = [
                q for q in self.dataset
                if q["difficulty"].lower() == difficulty.lower()
            ]
        
        # If still empty, relax difficulty
        if not candidates:
            candidates = [
                q for q in self.dataset
                if q["id"] not in self.used_question_ids
            ]
        
        if not candidates:
            candidates = self.dataset  # Last resort
        
        # Prefer topics not recently covered
        fresh_candidates = [
            q for q in candidates
            if q.get("category") not in topics_covered[-3:]  # Last 3 topics
        ]
        
        pool = fresh_candidates if fresh_candidates else candidates
        selected = random.choice(pool)
        
        # Mark as used
        self.used_question_ids.add(selected["id"])
        
        # Get the question (potentially rephrase for naturalness)
        question_text = self._maybe_rephrase_question(
            selected["question"],
            selected.get("category", "Software Engineering")
        )
        
        metadata = {
            "source": "dataset",
            "question_id": selected["id"],
            "category": selected.get("category", "Unknown"),
            "difficulty": selected.get("difficulty", "medium"),
            "reference_answer": selected.get("answer", ""),
            "is_followup": False
        }
        
        return question_text, metadata
    
    def generate_followup_question(
        self,
        previous_question: str,
        previous_answer: str,
        followup_angle: str,
        evaluation: Dict
    ) -> Tuple[str, Dict]:
        """
        Generate a FOLLOW-UP question based on previous Q&A
        
        This is where LLM shines - generating contextual probes
        
        Args:
            previous_question: The question candidate just answered
            previous_answer: Candidate's answer
            followup_angle: Type of follow-up (from FlowController)
            evaluation: Evaluation of previous answer
        
        Returns:
            (question_text, metadata)
        """
        
        # Build focused prompt for LLM
        system_prompt = self._get_followup_system_prompt(followup_angle)
        
        user_prompt = f"""Previous question: {previous_question}

Candidate's answer: {previous_answer}

Evaluation notes:
- Depth score: {evaluation.get('depth_score', 0.5):.2f}
- Pass: {evaluation.get('pass', False)}

Generate ONE natural follow-up question that probes deeper.
Rules:
1. Must be directly related to the previous answer
2. Maximum 25 words
3. Natural interview style (conversational)
4. No preamble - just the question
5. End with question mark

Question:"""

        try:
            response = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6,  # Some creativity for natural follow-ups
                max_tokens=80,
                top_p=0.9,
                repeat_penalty=1.1
            )
            
            question_text = response["choices"][0]["message"]["content"].strip()
            
            # Clean up
            question_text = self._clean_generated_question(question_text)
            
            # Validate
            if not self._is_valid_followup(question_text, previous_answer):
                # Fallback to template-based follow-up
                question_text = self._template_followup(
                    previous_answer, 
                    followup_angle
                )
        
        except Exception as e:
            print(f"⚠️ LLM follow-up generation failed: {e}")
            question_text = self._template_followup(
                previous_answer,
                followup_angle
            )
        
        metadata = {
            "source": "llm_generated",
            "is_followup": True,
            "followup_angle": followup_angle,
            "based_on_question": previous_question,
            "reference_answer": None  # No ground truth for follow-ups
        }
        
        return question_text, metadata
    
    def _get_followup_system_prompt(self, angle: str) -> str:
        """System prompts for different follow-up types"""
        
        base = """You are a senior and skilled technical interviewer for the following role:

Job Description:
{self.job_description}

Candidate Background (from resume):
{self.candidate_resume}

Your questions must be:
- Directly relevant to the JD requirements and candidate's real experience
- Probing and insightful
- Natural conversation style
        
Your follow-up questions must be:
- Direct and focused
- Build on the previous answer
- Test deeper understanding
- Natural and conversational
"""
        
        angle_specific = {
            "elaboration": "\nGoal: Get more detail and depth from their answer.",
            "clarification": "\nGoal: Clarify vague or ambiguous points.",
            "examples": "\nGoal: Request concrete examples or use cases.",
            "implementation_details": "\nGoal: Probe how they would actually implement or apply this.",
            "tradeoffs": "\nGoal: Explore alternatives, trade-offs, or limitations.",
            "edge_cases": "\nGoal: Test handling of edge cases or failure scenarios."
        }
        
        return base + angle_specific.get(angle, "")
    
    def _clean_generated_question(self, text: str) -> str:
        """Clean LLM-generated question text"""
        
        # Remove common artifacts
        text = re.sub(r'^(Question:|Follow-up:|Q:)\s*', '', text, flags=re.IGNORECASE)
        text = text.strip()
        
        # Ensure question mark
        if text and not text.endswith('?'):
            text += '?'
        
        # Take only first sentence if multiple
        sentences = re.split(r'[.!?]', text)
        if sentences:
            text = sentences[0].strip()
            if not text.endswith('?'):
                text += '?'
        
        return text
    
    def _is_valid_followup(self, question: str, previous_answer: str) -> bool:
        """Validate generated follow-up is reasonable"""
        
        # Basic checks
        if not question or len(question) < 10:
            return False
        
        if not question.endswith('?'):
            return False
        
        if len(question.split()) > 30:  # Too long
            return False
        
        # Check if question references something from answer
        # Simple heuristic: share at least one meaningful word
        q_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
        a_words = set(re.findall(r'\b\w{4,}\b', previous_answer.lower()))
        
        common_words = q_words & a_words
        
        # Should share at least 1-2 words (but not too many - that's copy-paste)
        if len(common_words) < 1 or len(common_words) > 10:
            return False
        
        return True
    
    def _template_followup(self, previous_answer: str, angle: str) -> str:
        """
        Fallback template-based follow-ups
        Used when LLM generation fails
        """
        
        templates = {
            "elaboration": [
                "Can you elaborate on that?",
                "Can you explain that in more detail?",
                "Could you expand on your answer?"
            ],
            "clarification": [
                "What exactly do you mean by that?",
                "Can you clarify that point?",
                "Could you be more specific?"
            ],
            "examples": [
                "Can you give me a concrete example?",
                "What's a practical use case for this?",
                "Can you show me how that would work in practice?"
            ],
            "implementation_details": [
                "How would you actually implement that?",
                "Walk me through your approach step by step.",
                "What would the code look like?"
            ],
            "tradeoffs": [
                "What are the trade-offs of that approach?",
                "How does this compare to alternatives?",
                "What are the downsides?"
            ],
            "edge_cases": [
                "What could go wrong with that approach?",
                "How would you handle edge cases?",
                "What if the input is invalid?"
            ]
        }
        
        options = templates.get(angle, templates["elaboration"])
        return random.choice(options)
    
    def _maybe_rephrase_question(self, question: str, category: str) -> str:
        """
        Optionally rephrase dataset question for variety
        
        Only rephrase ~30% of the time to maintain consistency
        """
        
        if random.random() > 0.3:
            return question  # Use as-is
        
        # Simple rephrasing: add conversational prefix
        prefixes = [
            "",  # No prefix
            "Let me ask you this: ",
            "Here's a question: ",
            "I'd like to know: ",
            "Quick question: "
        ]
        
        prefix = random.choice(prefixes)
        return f"{prefix}{question}"


# ========== USAGE EXAMPLE ==========
if __name__ == "__main__":
    # Mock data for testing
    mock_dataset = [
        {
            "id": 1,
            "question": "What is the difference between compilation and interpretation?",
            "answer": "Compilation translates source code into machine code...",
            "category": "General Programming",
            "difficulty": "medium"
        },
        {
            "id": 2,
            "question": "Explain polymorphism in OOP.",
            "answer": "Polymorphism allows objects of different types...",
            "category": "Object-Oriented Programming",
            "difficulty": "medium"
        }
    ]
    
    with open("data/temp/job_description.json") as f:
        job_desc = json.load(f)["text"]     
    with open("data/temp/sample_resume.json") as f:
        resume = json.load(f)["text"]
    
    generator = QuestionGenerator(
        llm=get_test_llm(),
        candidate_resume=resume,
        job_description=job_desc,
        dataset_questions=mock_dataset
    )
    
    # Test new topic question
    print("=== NEW TOPIC QUESTION ===")
    q, meta = generator.generate_new_topic_question(
        topics_covered=["algorithms"],
        difficulty="medium"
    )
    print(f"Question: {q}")
    print(f"Metadata: {meta}\n")
    
    # Test follow-up question
    print("=== FOLLOW-UP QUESTION ===")
    followup_q, followup_meta = generator.generate_followup_question(
        previous_question="What is the difference between compilation and interpretation?",
        previous_answer="Compilation is when you turn code into binary.",
        followup_angle="examples",
        evaluation={"pass": False, "depth_score": 0.4}
    )
    print(f"Follow-up: {followup_q}")
    print(f"Metadata: {followup_meta}")