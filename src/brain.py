from openai import OpenAI
from pydantic import BaseModel, Field
import os

# Define the output structure for the AI
class JobAnalysis(BaseModel):
    is_relevant: bool = Field(description="True if the job is suitable for 0-3 years experience. False if it's Senior/Staff/Lead.")
    years_required: int = Field(description="The minimum years of experience mentioned (0 if not specified).")
    tech_stack: list[str] = Field(description="The 3-5 main technologies mentioned.")
    reason: str = Field(description="One short sentence explaining why it is or isn't relevant.")

class JobBrain:
    def __init__(self):
        self.api_key = self._load_api_key()
        if not self.api_key:
            # We don't want to crash the whole app if the key is missing
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

    def _load_api_key(self):
        """Reads the key from the central authorization.txt file."""
        try:
            if not os.path.exists("authorization.txt"): return None
            with open("authorization.txt", "r") as f:
                for line in f:
                    if line.startswith("OPENAI_API_KEY="):
                        return line.split("=")[1].strip()
        except: return None
        return None

    def analyze(self, job_title, job_description):
        if not self.client:
            return None

        # We only send the first 1000 characters to save tokens/money
        clean_description = job_description[:1000].replace('\n', ' ')
        
        prompt = f"""
        Analyze this job for a Junior SWE (0-3 years experience).
        Title: {job_title}
        Description: {clean_description}
        
        Rules:
        1. Suitable = 0-3 years experience.
        2. Unsuitable = 4+ years, Lead, Staff, or Management.
        3. If it's a 'Student' or 'Intern' or 'Junior' or 'Assosicate' role, it is ALWAYS relevant.
        """

        try:
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini", # Cheapest and fastest for this task
                messages=[
                    {"role": "system", "content": "You are a tech recruiter in Israel filtering for Entry-level/Junior engineers."},
                    {"role": "user", "content": prompt},
                ],
                response_format=JobAnalysis,
            )
            return completion.choices[0].message.parsed
        except Exception as e:
            print(f"    [!] AI Analysis Error: {e}")
            return None