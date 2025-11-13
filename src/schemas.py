from pydantic import BaseModel, Field
from typing import List, Optional

# --- Resume Data Models ---

class Education(BaseModel):
    institution: str = Field(..., description="Name of the university or school")
    degree: str = Field(..., description="e.g., Bachelor of Science, High School Diploma")
    field_of_study: Optional[str] = Field(None, description="e.g., Computer Science")
    start_date: Optional[str] = Field(None, description="Start date, e.g., 'Aug 2020'")
    end_date: Optional[str] = Field(None, description="End date, e.g., 'May 2024' or 'Present'")
    gpa: Optional[float] = Field(None, description="Grade Point Average")

class Experience(BaseModel):
    company: str = Field(..., description="Name of the company")
    position: str = Field(..., description="Job title, e.g., 'Software Engineer Intern'")
    start_date: Optional[str] = Field(None, description="e.g., 'Jun 2023'")
    end_date: Optional[str] = Field(None, description="e.g., 'Aug 2023' or 'Present'")
    responsibilities: List[str] = Field(default_factory=list, description="List of key responsibilities or achievements")

class Project(BaseModel):
    name: str = Field(..., description="The name of the project")
    description: str = Field(..., description="A brief description of the project")
    technologies: List[str] = Field(default_factory=list, description="List of technologies used, e.g., 'Python', 'FastAPI'")
    link: Optional[str] = Field(None, description="A URL to the project repository or demo")

class Certification(BaseModel):
    name: str = Field(..., description="The name of the certificate")
    issuer: str = Field(..., description="The organization that issued it, e.g., 'Coursera', 'AWS'")
    date_issued: Optional[str] = Field(None, description="e.g., 'Jun 2023'")

class Achievement(BaseModel):
    description: str = Field(..., description="Description of the achievement, e.g., 'Won 1st place in Hackathon XYZ'")
    
class Skills(BaseModel):
    technical: List[str] = Field(default_factory=list, description="List of technical skills, e.g., 'Python', 'SQL'")
    soft: List[str] = Field(default_factory=list, description="List of soft skills, e.g., 'Communication'")

class ResumeData(BaseModel):
    """The main schema for all extracted resume data."""
    education: List[Education] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    achievements: List[Achievement] = Field(default_factory=list)
    skills: Optional[Skills] = Field(default_factory=Skills)

# --- API Request/Response Models ---

class StartChatRequest(BaseModel):
    user_id: str

class StartChatResponse(BaseModel):
    chat_id: str
    message: str

class ChatRequest(BaseModel):
    user_message: str

class ChatResponse(BaseModel):
    chat_id: str
    ai_response: str
    current_section: str
    is_complete: bool