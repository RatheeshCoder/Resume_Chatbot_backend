# database.py
import os
from bson import ObjectId
from pymongo import MongoClient
from typing import Optional, Any, Dict
from langgraph.checkpoint.memory import MemorySaver # Base class for checkpointer

# Assuming 'src.config' and 'settings' are correctly configured in your environment
try:
    from src.config import settings
except ImportError:
    class MockSettings:
        MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    settings = MockSettings()


client = None
chat_collection = None


def connect_to_db():
    global client, chat_collection
    mongo_uri = settings.MONGO_URI
    if not mongo_uri:
        # Fallback to a clear error if environment is not set
        raise ValueError("MONGO_URI not set. Check your .env file and config.py")

    try:
        # Connect to MongoDB with a timeout
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # The ismaster command is a cheap way to verify a connection
        client.admin.command('ping')
        print("✅ INFO: Successfully connected to MongoDB.")
        # Ensure the client is connected before getting the database
        db = client.get_database("resume_chatbot_db")
        chat_collection = db.get_collection("chat_sessions")
    except Exception as e:
        print(f"❌ ERROR: Failed to connect to MongoDB: {e}")
        # Ensure client is reset to None if connection fails
        client = None 
        chat_collection = None


def disconnect_db():
    global client
    if client:
        client.close()
        print("🔌 MongoDB disconnected.")


def create_chat_session(user_id: str, role: str = "user") -> str:
    if chat_collection is None:
        raise ConnectionError("❌ MongoDB collection not initialized. Call connect_to_db() first.")

    resume_data = {
        "education": [],
        "experience": [],
        "skills": [],
        "projects": [],
        "certifications": [],
        "achievements": []
    }

    chat_doc = {
        "user_id": user_id,
        "role": role,
        "messages": [],
        "langgraph_state": {},  # <-- New field for LangGraph Checkpoint
        "ready_for_resume": False,
        "resume_data": resume_data
    }

    result = chat_collection.insert_one(chat_doc)
    print(f"🟢 DEBUG: Created chat session for user_id={user_id}, chat_id={result.inserted_id}")
    return str(result.inserted_id)


def get_chat_session(chat_id: str):
    if chat_collection is None:
        return None
    try:
        return chat_collection.find_one({"_id": ObjectId(chat_id)})
    except Exception as e:
        print(f"⚠️ ERROR: Failed to fetch chat session {chat_id}: {e}")
        return None


def update_chat_session(chat_id: str, update_fields: Dict[str, Any]):
    """
    Updates fields in the chat session document.
    Example: update_chat_session(chat_id, {"resume_data.projects": projects_list})
    """
    if chat_collection is None:
        raise ConnectionError("❌ MongoDB collection not initialized.")

    try:
        chat_collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$set": update_fields}
        )
    except Exception as e:
        print(f"⚠️ ERROR: Failed to update chat session {chat_id}: {e}")


def append_message(chat_id: str, role: str, message: str, section: str = None):
    """✅ Works for both user & AI roles"""
    if chat_collection is None:
        raise ConnectionError("❌ MongoDB collection not initialized.")

    try:
        message_obj = {"role": role, "message": message}
        if section:
            message_obj["section"] = section

        chat_collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$push": {"messages": message_obj}}
        )
    except Exception as e:
        print(f"⚠️ ERROR: Failed to append message: {e}")


def get_conversation_history(chat_id: str) -> list:
    session = get_chat_session(chat_id)
    if session:
        return session.get("messages", [])
    return []

# --- Custom MongoDB Checkpointer for LangGraph ---

class MongoDBCustomCheckpointer(MemorySaver):
    """
    A custom checkpointer that stores the LangGraph state in the MongoDB chat session.
    It inherits from MemorySaver for a simpler implementation.
    """
    def __init__(self, db_client: MongoClient):
        super().__init__()
        # CRITICAL CHECK: Ensure db_client is not None
        if db_client is None:
             raise ValueError("db_client cannot be None. MongoDB connection failed.")
             
        self.db_client = db_client
        self.db = self.db_client.get_database("resume_chatbot_db")
        self.chat_collection = self.db.get_collection("chat_sessions")

    def get_state(self, thread_id: str) -> Optional[Any]:
        session = self.chat_collection.find_one(
            {"_id": ObjectId(thread_id)},
            {"langgraph_state": 1}
        )
        if session and session.get("langgraph_state"):
            return self._restore_state(session["langgraph_state"])
        return None

    def update_state(self, thread_id: str, state: Any) -> None:
        self.chat_collection.update_one(
            {"_id": ObjectId(thread_id)},
            {"$set": {"langgraph_state": self._get_serializable_state(state)}},
            upsert=True
        )