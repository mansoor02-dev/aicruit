import random
import re
from typing import List, Dict, Tuple
from pipelines.llm_loader import LLMLoader
import json


class QuestionGenerator:
    def __init__(
        self,
        dataset_questions: List[Dict],
        model_type: str = 'openrouter',
        candidate_resume: str = "",    
        difficulty: str = "easy",
        retriever=None
    ):
        self.dataset = dataset_questions
        # Only initialize LLM if not provided (lazy initialization)
        self.llm = LLMLoader(model_type=model_type).get_llm()
        self.candidate_resume = candidate_resume      
        self.retriever = retriever
        self.difficulty = difficulty
        # Cache used questions to avoid repetition
        self.used_question_ids = set()
    
    def generate_new_topic_question(
        self,
        topics_covered: List[str] = None,
        difficulty: str = None,
        resume_json: Dict = None,
        evaluation_result: Dict = None
    ) -> Tuple[str, Dict]:
        """
        Generate a NEW TOPIC question (not a follow-up)
        
        Strategy:
        1. Filter dataset by difficulty
        2. Avoid recently covered topics
        3. Pick a question from dataset as inspiration
        4. Use LLM to generate/rephrase for resume/job context (optional)
        
        Args:
            topics_covered: List of topics already discussed
            difficulty: Desired difficulty level
            resume_json: Candidate resume dict (injected at generation time)
            evaluation_result: Previous evaluation result (optional context)
        
        Returns:
            (question_text, metadata)
        """
        topics_covered = topics_covered or []
        difficulty = difficulty or self.difficulty
        
        candidates = [
            q for q in self.dataset 
            if (q.get("Difficulty", "")).lower() == difficulty.lower()
            and (q.get("Id") not in self.used_question_ids)
        ]

        if len(candidates) < 3:
            candidates = [
                q for q in self.dataset
                if (q.get("Difficulty", "")).lower() == difficulty.lower()
            ]
        
        # If still empty, relax difficulty
        if not candidates:
            candidates = [
                q for q in self.dataset
                if (q.get("Id") not in self.used_question_ids)
            ]
        
        if not candidates:
            candidates = self.dataset  # Last resort
        
        # Prefer topics not recently covered
        fresh_candidates = [
            q for q in candidates
            if q.get("Category") not in topics_covered[-3:]  # Last 3 topics
        ]
        
        pool = fresh_candidates if fresh_candidates else candidates
        selected = random.choice(pool)
        
        # Mark as used
        selected_id = selected.get("Id")
        if selected_id is not None:
            self.used_question_ids.add(selected_id)
        
        # Get the question (use dataset or LLM-rephrase if resume available)
        if resume_json:
            # LLM-generated based on candidate context
            base_q = selected.get("Question", selected.get("question", ""))
            question_text = self._generate_contextual_question(
                base_question=base_q,
                category=selected.get("Category", "Software Engineering"),
                resume_json=resume_json,
                # evaluation_result=evaluation_result
            )
        else:
            # Use dataset question with optional rephrasing
            question_text = self._maybe_rephrase_question(
                selected.get("Question", selected.get("question", "")),
            )
        
        metadata = {
            "source": "dataset_inspired" if (resume_json) else "dataset",
            "question_id": selected.get("Id"),
            "category": selected.get("Category", "Unknown"),
            "difficulty": selected.get("Difficulty", "medium"),
            "reference_answer": selected.get("Answer", ""),
            "is_followup": False
        }
        
        return question_text, metadata
    
    def generate_followup_question(
        self,
        previous_question: str,
        previous_answer: str,
        resume_json: Dict = None,
        evaluation_result: Dict = None,
    ) -> Tuple[str, Dict]:
        """
        Generate a FOLLOW-UP question based on previous Q&A
        
        This is where LLM shines - generating contextual probes
        
        Args:
            previous_question: The question candidate just answered
            previous_answer: Candidate's answer
            resume_json: Candidate resume dict (for contextual probes)
            evaluation_result: Evaluation of previous answer (contains decision/score)
        
        Returns:
            (question_text, metadata)
        """
        
        # Determine followup angle from evaluation decision
        if evaluation_result:
            decision = evaluation_result.get("decision", "same_topic").lower()
        else:
            decision = "same_topic"
        
        # Map decision to followup angle
        if decision == "deep_dive":
            followup_angle = "implementation_details"
        elif decision == "same_topic":
            followup_angle = "elaboration"
        else:
            followup_angle = "elaboration"
        
        system_prompt = self._get_followup_system_prompt(
            followup_angle,
            resume_json,
        )
        
        user_prompt = f"""Previous question: {previous_question}

Candidate's answer: {previous_answer}

"""
        
        if evaluation_result:
            user_prompt += f"""Evaluation:
- Decision: {evaluation_result.get('decision', 'unknown')}
- Score: {evaluation_result.get('score_value', 0.5):.2f}
- Remarks: {evaluation_result.get('remarks', '')}

"""
        
        user_prompt += """Generate ONE natural follow-up question that probes deeper.
Rules:
1. Must be directly related to the previous answer
2. Maximum 25 words
3. Natural interview style (conversational)
4. No preamble - just the question
5. End with question mark

Question:"""

        try:
            response = self.llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6,  # Some creativity for natural follow-ups
                max_tokens=150,
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
                    # previous_answer, 
                    followup_angle
                )
        
        except Exception as e:
            print(f"⚠️ LLM follow-up generation failed: {e}")
            question_text = self._template_followup(
                # previous_answer,
                followup_angle
            )
        
        metadata = {
            "source": "llm_generated",
            "is_followup": True,
            "followup_angle": followup_angle,
            "based_on_question": previous_question,
            "reference_answer": None,  # No ground truth for follow-ups
            "includes_previous_qa": True
        }
        
        return question_text, metadata
    
    def _get_followup_system_prompt(self, angle: str, resume_json: Dict = None) -> str:
        """System prompts for different follow-up types"""
        
        resume_context = ""
        if resume_json:
            # Extract key resume info to include in prompt
            resume_str = json.dumps(resume_json)[:500] if isinstance(resume_json, dict) else str(resume_json)[:500]
            resume_context = f"\nCandidate Resume (Summary):\n{resume_str}\n"
        
        base = f"""You are a senior and skilled technical interviewer.

{resume_context}

Your follow-up questions must be:
- Directly relevant to the candidate's background and the JD requirements
- Probing and insightful but conversational
- Build naturally on their previous answer
- Test depth of understanding
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
    
    def _generate_contextual_question(
        self,
        base_question: str,
        category: str,
        resume_json: Dict = None,
    ) -> str:
        """
        Use LLM to generate a contextual question based on base question + resume + job
        
        Args:
            base_question: Base question from dataset
            category: Question category
            resume_json: Candidate resume
            evaluation_result: Optional evaluation context
        
        Returns:
            LLM-generated question text
        """
        
        resume_str = json.dumps(resume_json)[:300] if resume_json and isinstance(resume_json, dict) else ""
        
        system_prompt = f"""You are a senior technical interviewer. Your questions must be:
- Tailored to the candidate's background and the job requirements
- Relevant to their specific experience
- Natural and conversational
- Technically sound

Candidate Resume: {resume_str}

"""
        
        user_prompt = f"""Base question template: {base_question}

Category: {category}

Generate ONE specific, natural interview question for this candidate based on their resume and the job.
- Personalize it to their background
- Example templates: "You mentioned X in your resume. Tell me about..."
- No preamble, just the question
- End with question mark
- 15-30 words

Question:"""
        
        try:
            response = self.llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            question_text = response["choices"][0]["message"]["content"].strip()
            question_text = self._clean_generated_question(question_text)
            
            # Validate length
            if len(question_text.split()) > 35:
                # Too long, fallback to base question
                return self._maybe_rephrase_question(base_question, category)
            
            return question_text
        
        except Exception as e:
            print(f"⚠️ Contextual question generation failed: {e}")
            return self._maybe_rephrase_question(base_question, category)
    
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
    
    def _template_followup(self, angle: str) -> str:
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
    
    def _maybe_rephrase_question(self, question: str) -> str:
        """
        Optionally rephrase dataset question for variety
        
        Only rephrase ~30% of the time to maintain consistency
        """
        
        if random.random() > 0.4:
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
            "Id": 1,
            "Question": "What is the difference between compilation and interpretation?",
            "Answer": "Compilation translates source code into machine code...",
            "Category": "General Programming",
            "Difficulty": "medium"
        },
        {
            "Id": 2,
            "Question": "Explain polymorphism in OOP.",
            "Answer": "Polymorphism allows objects of different types...",
            "Category": "Object-Oriented Programming",
            "Difficulty": "medium"
        }
    ]
    
    # with open("data/temp/job_description.json") as f:
    #     job_desc = json.load(f)["job_description"]    
    with open("data/temp/sample_resume.json") as f:
        resume = json.load(f)
    
    generator = QuestionGenerator(
        model_type="gemini",
        candidate_resume=resume,
        dataset_questions=mock_dataset,
        difficulty="easy"
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
        previous_answer="I am not fimiliar with those concepts.",
        resume_json=resume,
        evaluation_result={"pass": False, "depth_score": 0.4}
    )
    print(f"Follow-up: {followup_q}")
    print(f"Metadata: {followup_meta}")