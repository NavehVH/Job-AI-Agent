from openai import OpenAI
from pydantic import BaseModel, Field
import os

# Define the output structure for the AI
class JobAnalysis(BaseModel):
    is_junior: bool = Field(description="True if the job requires 0-3 years experience. False if Senior/Lead.")
    years_required: int = Field(description="The minimum years of experience mentioned (use 0 for none).")
    tech_stack: list[str] = Field(description="List of main technologies mentioned.")
    reason: str = Field(description="A short sentence explaining why it is or isn't a junior role.")

class JobBrain:
    def __init__(self):
        self.api_key = self._load_api_key()
        if not self.api_key:
            raise ValueError("Could not find API Key in 'openai_key.txt' or environment variables!")
            
        self.client = OpenAI(api_key=self.api_key)

    def _load_api_key(self):
        """Tries to load key from file first, then environment variable."""
        # 1. Try reading the file "openai_key.txt"
        try:
            with open("openai_key.txt", "r") as f:
                key = f.read().strip()
                if key.startswith("sk-"):
                    return key
        except FileNotFoundError:
            pass

        # 2. Fallback to Environment Variable
        return os.getenv("OPENAI_API_KEY")

    def analyze(self, job_title, job_description):
        prompt = f"""
        Role: {job_title}
        Description Context: {job_description[:500]} 
        
        Analyze if this is a JUNIOR role suitable for a graduate or 0-3 years experience.
        Ignore 'Senior' in the title if the description says 0-2 years.
        Reject if it requires 4+ years.
        """

        try:
            completion = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a strict tech recruiter looking for Junior/Entry-level roles in Israel."},
                    {"role": "user", "content": prompt},
                ],
                response_format=JobAnalysis,
            )
            return completion.choices[0].message.parsed
            
        except Exception as e:
            print(f"[!] AI Error: {e}")
            return None