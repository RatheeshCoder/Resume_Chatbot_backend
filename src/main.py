from fastapi import FastAPI
from contextlib import asynccontextmanager

import src.database as db
from src.project_route import router as project_router 
from src.experience_route import router as experience_router 
from src.education_route import router as education_router 
from src.achievements_route import router as achievements_router 
from src.skills_route import router as skills_router 

from fastapi.middleware.cors import CORSMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    # initialize DB connection at startup and close at shutdown
    db.connect_to_db()
    yield
    db.disconnect_db()

app = FastAPI(
    title="Resume Project Chatbot API",
    description="Conversational Project Collector for Resume Builder.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173" ,"https://resume-chatbot-frontend.onrender.com"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the router under the requested base path
# All endpoints in route.py will be available under /api/v1/chatbot/project
app.include_router(project_router, prefix="/api/v1/chatbot/project")
app.include_router(experience_router, prefix="/api/v1/chatbot/experience")
app.include_router(education_router, prefix="/api/v1/chatbot/education")
app.include_router(achievements_router, prefix="/api/v1/chatbot/achievements")
app.include_router(skills_router, prefix="/api/v1/chatbot/skills")
