def get_schema_description() -> str:
    """Generate schema description for LLM"""
    return """
You are an expert resume parser. Extract information into this EXACT JSON structure:

{
  "name": "Full name",
  "email": "email@example.com",
  "phone": "+1-234-567-8900",
  "location": "City, Country",
  "linkedin": "https://linkedin.com/in/username",
  "github": "https://github.com/username",
  "website": "https://personal-site.com",
  "summary": "Professional summary in 2-3 sentences",
  
  "skills": ["Python", "Machine Learning", "TensorFlow", "AWS", "Docker"],
  
  "education": [
    {
      "degree": "MSc",
      "field": "Computer Science",
      "university": "Stanford University",
      "country": "USA",
      "start_year": 2020,
      "end_year": 2022,
      "gpa": 3.9
    }
  ],
  
  "experience": [
    {
      "title": "Senior Software Engineer",
      "company": "Google",
      "location": "Mountain View, CA",
      "start_date": "2022-06",
      "end_date": "Present",
      "duration_months": 24,
      "description": "Led team of 5 engineers...",
      "technologies": ["Python", "Kubernetes", "GCP"]
    }
  ],
  
  "projects": [
    {
      "title": "ML Pipeline for CV Screening",
      "description": "Built automated screening system",
      "technologies": ["Python", "PyTorch", "FastAPI"],
      "role": "Lead Developer",
      "link": "https://github.com/user/project",
      "year": 2023
    }
  ],
  
  "publications": [
    {
      "title": "Attention Mechanisms in NLP",
      "authors": ["John Doe", "Jane Smith"],
      "venue": "NeurIPS 2023",
      "year": 2023,
      "paper_type": "conference",
      "link": "https://arxiv.org/abs/..."
    }
  ],
  
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect",
      "issuer": "Amazon Web Services",
      "issue_date": "2023-01",
      "expiry_date": "2026-01",
      "credential_id": "ABC123"
    }
  ],
  
  "languages": ["English (Native)", "Spanish (Fluent)"],
  "awards": ["Best Paper Award NeurIPS 2023", "Dean's List"]
}

CRITICAL RULES:
1. Return ONLY valid JSON (no markdown, no explanation)
2. If information is missing, use null or empty array []
3. For dates, use "YYYY-MM" format
4. For "end_date", use "Present" if currently employed
5. Extract ALL skills mentioned (programming languages, frameworks, tools)
6. Be precise with company names, universities, and paper venues
7. If GPA is not on 4.0 scale, convert it (e.g., 3.5/4.0)
"""

