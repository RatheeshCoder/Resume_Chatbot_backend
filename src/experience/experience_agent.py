import json
import re
from datetime import datetime
from typing import TypedDict, Annotated, List, Optional, Dict, Any, Literal
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Internal imports
from src.config import settings
import src.database as db
from src.database import MongoDBCustomCheckpointer
# ============================================================
# ✅ IMPORT *EXPERIENCE* PROMPTS
# (Assuming prompts are in a parallel file: src.prompts_experience.py)
# ============================================================
from src.experience.experience_prompt import (
    EXPERIENCE_FIELD_AGENT_PROMPTS as FIELD_AGENT_PROMPTS,
    EXPERIENCE_QUESTION_GENERATOR_PROMPTS as QUESTION_GENERATOR_PROMPTS,
    RE_ASK_PHRASES,
    EXPERIENCE_ACKNOWLEDGMENT_PHRASES as ACKNOWLEDGMENT_PHRASES,
    EXPERIENCE_CHATBOT_METADATA as CHATBOT_METADATA
)

# ============================================================
# ✅ INITIALIZE DB CONNECTION
# ============================================================
try:
    db.connect_to_db()
except Exception as e:
    print(f"FATAL ERROR: Could not connect to MongoDB. {e}")

# ============================================================
# ✅ FIELD DEFINITIONS - SEQUENTIAL ORDER (FOR EXPERIENCE)
# ============================================================
# User-provided fields
ALL_FIELDS = [
    'title', 
    'organization_name', 
    'type', 
    'timeline', 
    'what_you_did', 
    'how_you_did_it', 
    'domain_or_field', 
    'tools_and_technologies', 
    'role_and_responsibilities', 
    'outcomes_or_achievements',
    'skills_gained'
]

# Define mandatory/optional based on new fields
MANDATORY_FIELDS = [
    'title', 
    'organization_name', 
    'type', 
    'timeline', 
    'role_and_responsibilities'
]
OPTIONAL_FIELDS = [f for f in ALL_FIELDS if f not in MANDATORY_FIELDS]


# Define skip phrases
SKIP_PHRASES = [
    "skip", "i don't know", "don't know", "n/a", "na",
    "not applicable", "none", "nothing"
]

# Define positive/negative confirmation phrases
CONFIRM_YES = ["yes", "ok", "correct", "submit", "looks good", "yep"]
CONFIRM_NO = ["no", "edit", "change", "wrong", "nope"]

# ============================================================
# ✅ DATA MODELS (Unchanged - Generic)
# ============================================================
class FieldExtractionResult(BaseModel):
    field_name: str = Field(..., description="Name of the field")
    extracted_value: Any = Field(None, description="Extracted value")
    is_complete: bool = Field(False, description="Has meaningful data?")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in the extraction (0.0 to 1.0)")
    reasoning: str = Field(..., description="Chain-of-thought reasoning for the extraction decision")
    needs_clarification: bool = Field(False, description="True if the user's input was ambiguous for this field")
    clarification_reason: Optional[str] = Field(None, description="Reason why clarification is needed")

class FieldQuestionGeneration(BaseModel):
    field_name: str = Field(..., description="Field name")
    question: str = Field(..., description="Natural question")
    follow_up_prompts: List[str] = Field(default_factory=list, description="Optional list of example user replies")
    reasoning: str = Field(..., description="Why this question was generated")

class UserIntentClassification(BaseModel):
    intent: Literal[
        "answer_question",
        "request_summary",
        "request_clarification",
        "request_done",
        "off_topic"
    ] = Field(..., description="The primary intent of the user's message")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the classification")
    reasoning: str = Field(..., description="Why this intent was identified")
    clarification_topic: Optional[str] = Field(None, description="Clarification topic if user is confused")

class ClarificationResponse(BaseModel):
    explanation: str = Field(..., description="Explanation for the user’s confusion")
    example: Optional[str] = Field(None, description="Example if helpful")
    follow_up_question: str = Field(..., description="Re-ask question in simpler form")

# ============================================================
# ✅ GRAPH STATE (FOR EXPERIENCE)
# ============================================================
def merge_experience_data(left: dict, right: dict) -> dict:
    if right is None:
        return left
    if left is None:
        return right
    merged = {**left, **right}
    print(f"🔄 MERGE: left={left}, right={right}, result={merged}")
    return merged

class ExperienceGraphState(TypedDict):
    chat_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    current_experience: Annotated[dict, merge_experience_data]
    experiences_collected: List[dict]
    field_completion_status: Dict[str, bool]
    field_ask_count: Dict[str, int]
    current_field: Optional[str]
    conversation_context: str
    interaction_count: int
    is_first_message: bool
    awaiting_confirmation: Optional[bool]
    awaiting_field_to_edit: Optional[bool]

# ============================================================
# ✅ DYNAMIC LLM INITIALIZATION
# ============================================================
def get_llm(api_key: str):
    """Dynamically create ChatGroq using the provided frontend API key."""
    if not api_key:
        raise ValueError("Missing LLM API key for this session.")
    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=api_key,
        temperature=0.1
    )

def init_experience_agents_with_llm(llm):
    """Bind all field/intent/clarification agents dynamically."""
    EXPERIENCE_FIELD_EXTRACTOR_AGENTS = {
        f: llm.bind_tools([convert_to_openai_tool(FieldExtractionResult)], tool_choice="FieldExtractionResult")
        for f in ALL_FIELDS
    }
    EXPERIENCE_FIELD_QUESTION_AGENTS = {
        f: llm.bind_tools([convert_to_openai_tool(FieldQuestionGeneration)], tool_choice="FieldQuestionGeneration")
        for f in ALL_FIELDS
    }
    EXPERIENCE_INTENT_CLASSIFIER = llm.bind_tools([convert_to_openai_tool(UserIntentClassification)], tool_choice="UserIntentClassification")
    EXPERIENCE_CLARIFICATION_GENERATOR = llm.bind_tools([convert_to_openai_tool(ClarificationResponse)], tool_choice="ClarificationResponse")
    return EXPERIENCE_FIELD_EXTRACTOR_AGENTS, EXPERIENCE_FIELD_QUESTION_AGENTS, EXPERIENCE_INTENT_CLASSIFIER, EXPERIENCE_CLARIFICATION_GENERATOR

# ============================================================
# ✅ INTENT CLASSIFICATION SYSTEM (FOR EXPERIENCE)
# ============================================================
EXPERIENCE_INTENT_CLASSIFIER_PROMPT = """You are an intent classification agent for a conversational resume builder chatbot.

<CHATBOT_CONTEXT>
{metadata}
</CHATBOT_CONTEXT>

<YOUR_TASK>
Analyze the user's message and determine their PRIMARY INTENT from these categories:

1. **answer_question**: User is providing information in response to the bot's question
    - Examples: "I was a Software Engineer", "At Google", "Jan 2023 to Present"
    
2. **request_summary**: User wants to know what information has been collected so far
    - Examples: "what do you have so far?", "can you show me what we've covered?", "recap please"
    - Note: This is NOT the same as asking about the field being discussed
    
3. **request_clarification**: User doesn't understand the current question/field/concept
    - Examples: "what do you mean by outcome?", "I don't understand", "what's 'domain'?"
    - This includes meta-questions about the process itself
    
4. **request_done**: User wants to stop or finish the conversation early
    - Examples: "that's all", "I'm done", "let's finish", "stop"
    
5. **off_topic**: User is discussing something unrelated to the task
    - Examples: "how's the weather?", "tell me a joke"

<IMPORTANT>
- Focus on the PRIMARY intent, not secondary meanings
- Be confident in common patterns
- For ambiguous cases, default to "answer_question" if they seem to be providing information
- Mark confidence < 0.7 if truly ambiguous
</IMPORTANT>
</YOUR_TASK>"""

def classify_user_intent_experience(
    user_message: str, 
    current_field: Optional[str],
    conversation_history: List[BaseMessage],
    experience_data: dict
) -> UserIntentClassification:
    """
    Uses LLM to classify the user's intent instead of keyword matching.
    """
    # Build context
    metadata_str = json.dumps(CHATBOT_METADATA, indent=2)
    
    recent_history = "\n".join([
        f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" 
        for m in conversation_history[-6:]
    ])
    
    experience_context = json.dumps(experience_data, indent=2) if experience_data else "No data collected yet"
    
    prompt = f"""<CONVERSATION_HISTORY>
{recent_history}
</CONVERSATION_HISTORY>

<CURRENT_FIELD_BEING_ASKED>
{current_field or 'None - just starting'}
</CURRENT_FIELD_BEING_ASKED>

<EXPERIENCE_DATA_SO_FAR>
{experience_context}
</EXPERIENCE_DATA_SO_FAR>

<USER_MESSAGE>
{user_message}
</USER_MESSAGE>

Classify the user's intent based on their message."""

    try:
        result = EXPERIENCE_INTENT_CLASSIFIER.invoke([
            SystemMessage(content=EXPERIENCE_INTENT_CLASSIFIER_PROMPT.format(metadata=metadata_str)),
            HumanMessage(content=prompt)
        ])
        
        if not result.tool_calls:
            print(f"⚠️ No tool call for intent classification. Response: {result.content}")
            # Default fallback
            return UserIntentClassification(
                intent="answer_question",
                confidence=0.5,
                reasoning="Fallback due to tool call failure"
            )
        
        args = result.tool_calls[0]["args"]
        classification = UserIntentClassification(**args)
        
        print(f"🎯 INTENT: {classification.intent} (confidence: {classification.confidence:.2f})")
        print(f"   Reasoning: {classification.reasoning}")
        
        return classification
        
    except Exception as e:
        print(f"❌ Intent classification error: {e}")
        return UserIntentClassification(
            intent="answer_question",
            confidence=0.3,
            reasoning=f"Error during classification: {str(e)}"
        )

# ============================================================
# ✅ CLARIFICATION GENERATION SYSTEM (FOR EXPERIENCE)
# ============================================================
EXPERIENCE_CLARIFICATION_GENERATOR_PROMPT = """You are a helpful clarification agent for a resume builder chatbot.

<CHATBOT_CONTEXT>
{metadata}
</CHATBOT_CONTEXT>

<YOUR_TASK>
The user is confused or asking for clarification. Your job is to:

1. **Explain** the concept, field, or process they're asking about clearly and concisely
2. **Provide an example** if helpful (especially for abstract concepts)
3. **Re-ask** the original question in a clearer, more accessible way

<GUIDELINES>
- Be friendly and encouraging
- Use simple language
- Provide concrete examples from common job experiences
- Don't be condescending
- Keep explanations brief (2-3 sentences max)
- Make the re-asked question easier to understand than the original
</GUIDELINES>
</YOUR_TASK>"""

def generate_clarification_response_experience(
    user_message: str,
    current_field: str,
    clarification_topic: Optional[str],
    conversation_history: List[BaseMessage],
    experience_data: dict
) -> ClarificationResponse:
    """
    Uses LLM to generate contextual clarification instead of static templates.
    """
    metadata_str = json.dumps(CHATBOT_METADATA, indent=2)
    
    field_info = CHATBOT_METADATA["fields_we_collect"].get(
        current_field, 
        "Information about your experience"
    )
    
    recent_history = "\n".join([
        f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" 
        for m in conversation_history[-4:]
    ])
    
    prompt = f"""<RECENT_CONVERSATION>
{recent_history}
</RECENT_CONVERSATION>

<CURRENT_FIELD>
Field Name: {current_field}
Field Purpose: {field_info}
</CURRENT_FIELD>

<USER_CONFUSION>
User Message: {user_message}
What they're confused about: {clarification_topic or 'The current question/field'}
</USER_CONFUSION>

<EXPERIENCE_DATA_SO_FAR>
{json.dumps(experience_data, indent=2) if experience_data else 'Just starting'}
</EXPERIENCE_DATA_SO_FAR>

Generate a helpful clarification that addresses their confusion."""

    try:
        result = EXPERIENCE_CLARIFICATION_GENERATOR.invoke([
            SystemMessage(content=EXPERIENCE_CLARIFICATION_GENERATOR_PROMPT.format(metadata=metadata_str)),
            HumanMessage(content=prompt)
        ])
        
        if not result.tool_calls:
            print(f"⚠️ No tool call for clarification. Response: {result.content}")
            # Fallback
            return ClarificationResponse(
                explanation=f"I'm asking about the {current_field.replace('_', ' ')} of your job experience.",
                example=None,
                follow_up_question=f"Could you tell me about the {current_field.replace('_', ' ')}?"
            )
        
        args = result.tool_calls[0]["args"]
        clarification = ClarificationResponse(**args)
        
        print(f"💡 CLARIFICATION GENERATED:")
        print(f"   Explanation: {clarification.explanation}")
        print(f"   Example: {clarification.example}")
        
        return clarification
        
    except Exception as e:
        print(f"❌ Clarification generation error: {e}")
        return ClarificationResponse(
            explanation=f"I'm trying to understand the {current_field.replace('_', ' ')} of your experience better.",
            example=None,
            follow_up_question=f"Can you tell me more about the {current_field.replace('_', ' ')}?"
        )

# ============================================================
# ✅ HELPER FUNCTIONS (FOR EXPERIENCE)
# ============================================================
def is_field_data_present(value: Any) -> bool:
    """Check if the extracted value is actually meaningful data."""
    if value is None: return False
    if isinstance(value, str): return bool(value.strip())
    if isinstance(value, (list, dict)): return bool(value)
    if isinstance(value, (int, float)): return True
    return False

def get_next_experience_field_to_collect(completion: Dict[str, bool]) -> Optional[str]:
    """Get next field in sequential order"""
    for f in ALL_FIELDS:
        if not completion.get(f, False):
            return f
    return None

def get_random_experience_acknowledgment(field: str) -> str:
    """Get a varied acknowledgment phrase for the field"""
    import random
    phrases = ACKNOWLEDGMENT_PHRASES.get(field, ["Thanks!", "Got it."])
    return random.choice(phrases)

def get_re_ask_phrase(attempt: int) -> str:
    """Get a varied re-ask phrase based on attempt number"""
    import random
    if attempt == 1:
        return random.choice(RE_ASK_PHRASES["first"])
    else:
        return random.choice(RE_ASK_PHRASES["second"])

def send_experience_message(chat_id: str, content: str) -> AIMessage:
    """Helper to create an AIMessage and log it to the database."""
    msg = AIMessage(content=content)
    try:
        db.append_message(chat_id, "ai", content, "experiences")
    except Exception as e:
        print(f"Message log error: {e}")
    return msg

def save_experience_to_db(chat_id: str, experience: dict):
    """Saves the completed experience to the chat session in MongoDB."""
    try:
        chat = db.get_chat_session(chat_id)
        experiences = [experience] 
        db.update_chat_session(chat_id, {"resume_data.experiences": experiences})
        print(f"✅ Experience saved: {experience.get('title')}")
        return True
    except Exception as e:
        print(f"❌ Save error: {e}")

def format_experience_summary(experience: dict) -> str:
    """Formats a single experience dictionary into a readable string."""
    lines = [f"\n**{experience.get('title', 'Untitled Experience')} at {experience.get('organization_name', 'Unnamed Organization')}**"]
    for f in ALL_FIELDS:
        # Skip title/org since they are in the header
        if f in ['title', 'organization_name']:
            continue
            
        v = experience.get(f)
        if is_field_data_present(v):
            key_name = f.replace('_', ' ').title()
            if isinstance(v, list):
                lines.append(f"- {key_name}: {', '.join(map(str, v))}")
            elif isinstance(v, dict):
                start = v.get('start_date', '')
                end = v.get('end_date', 'Present')
                lines.append(f"- {key_name}: {start} - {end}")
            else:
                lines.append(f"- {key_name}: {v}")
    return "\n".join(lines)

def clean_user_input(text: str) -> str:
    """Utility to clean common low-effort phrases for matching."""
    return re.sub(r'[^\w\s]', '', text).strip().lower()

# ============================================================
# ✅ AGENT FUNCTIONS (FOR EXPERIENCE)
# ============================================================
def extract_experience_field_with_agent(field: str, messages: List[BaseMessage], current: Any) -> FieldExtractionResult:
    """Invokes the appropriate field extraction agent."""
    agent = EXPERIENCE_FIELD_EXTRACTOR_AGENTS[field]
    history = "\n".join([f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" for m in messages[-10:]])
    
    if field == "timeline":
        current_date = datetime.now().strftime('%B %d, %Y')
        system_prompt = FIELD_AGENT_PROMPTS[field].replace(
            "<CURRENT_DATE> is \"November 5, 2025\"", 
            f"<CURRENT_DATE> is \"{current_date}\""
        )
    else:
        system_prompt = FIELD_AGENT_PROMPTS[field]
        
    prompt = f"""<CONVERSATION_HISTORY>
{history}
</CONVERSATION_HISTORY>

<FIELD_TO_EXTRACT>{field}</FIELD_TO_EXTRACT>
<CURRENT_VALUE>{json.dumps(current)}</CURRENT_VALUE>

Based *only* on the user's *latest* message, extract information for the
field '{field}'. Follow all rules from the system prompt.
"""

    try:
        result = agent.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
        
        if not result.tool_calls:
            print(f"⚠️ No tool call for {field}. Agent response: {result.content}")
            raise Exception("No tool call made by agent.")
            
        args = result.tool_calls[0]["args"]
        args["field_name"] = field 
        extraction = FieldExtractionResult(**args)
        
        print(f"📊 [{field}] Extracted: {extraction.extracted_value}, Complete: {extraction.is_complete}, Confidence: {extraction.confidence}")
        return extraction
    except Exception as e:
        print(f"❌ Extract error {field}: {e}")
        return FieldExtractionResult(
            field_name=field, 
            extracted_value=current, 
            is_complete=bool(is_field_data_present(current)),
            confidence=0.0, 
            reasoning=f"Extraction failed: {str(e)}", 
            needs_clarification=False
        )

def generate_experience_question_with_agent(field: str, messages: List[BaseMessage], experience: dict, count: int) -> FieldQuestionGeneration:
    """Invokes the appropriate question generation agent."""
    agent = EXPERIENCE_FIELD_QUESTION_AGENTS[field]
    history = "\n".join([f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" for m in messages[-5:]])
    known = json.dumps({k: v for k, v in experience.items() if is_field_data_present(v)}, indent=2)
    
    prompt = f"""<RECENT_CONVERSATION>
{history}
</RECENT_CONVERSATION>

<KNOWN_EXPERIENCE_DATA>
{known}
</KNOWN_EXPERIENCE_DATA>

<FIELD_TO_ASK_FOR>{field}</FIELD_TO_ASK_FOR>
<TIMES_ASKED>{count}</TIMES_ASKED>

Generate a natural, conversational question to collect the '{field}' information.
Follow all rules from the system prompt.
"""

    try:
        result = agent.invoke([SystemMessage(content=QUESTION_GENERATOR_PROMPTS[field]), HumanMessage(content=prompt)])
        
        if not result.tool_calls:
            print(f"⚠️ No tool call for {field} question. Agent response: {result.content}")
            raise Exception("No tool call made by agent.")
            
        args = result.tool_calls[0]["args"]
        args["field_name"] = field
        return FieldQuestionGeneration(**args)
    except Exception as e:
        print(f"❌ Question error {field}: {e}")
        return FieldQuestionGeneration(
            field_name=field, 
            question=f"Could you tell me about the {field.replace('_', ' ')} of your experience?", 
            follow_up_prompts=[],
            reasoning="Fallback question due to generation error."
        )

# ============================================================
# ✅ NODES (UPDATED FOR EXPERIENCE)
# ============================================================
def start_experience_node(state: ExperienceGraphState) -> ExperienceGraphState:
    """
    Called only on the very first interaction.
    Initializes state and sends the welcome message.
    """
    print("\n🚀 START EXPERIENCE NODE")
    msg = send_experience_message(state["chat_id"], "Let's talk about one of your professional experiences. What was your job title for the role you'd like to add?")
    
    new_state = {
        **state,
        "messages": state.get("messages", []) + [msg],
        "current_experience": {},
        "experiences_collected": [],
        "field_completion_status": {f: False for f in ALL_FIELDS},
        "field_ask_count": {f: 0 for f in ALL_FIELDS},
        "is_first_message": False,
        "interaction_count": 0,
        "current_field": "title", 
        "awaiting_confirmation": False,
        "awaiting_field_to_edit": False,
    }
    print(f"📦 Initialized state with empty experience: {new_state['current_experience']}")
    return new_state

def process_experience_input_node(state: ExperienceGraphState) -> ExperienceGraphState:
    """
    Main processing node with LLM-based intent classification.
    """
    print(f"\n🔄 PROCESS EXPERIENCE INPUT NODE (Iteration {state.get('interaction_count', 0) + 1})")
    
    latest_msg_content = ""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            latest_msg_content = m.content
            break
            
    if not latest_msg_content:
        print("⚠️ No human message found. Ending.")
        return state

    latest_msg_clean = clean_user_input(latest_msg_content)
    
    experience = dict(state.get("current_experience", {})) if state.get("current_experience") else {}
    completion = dict(state.get("field_completion_status", {})) if state.get("field_completion_status") else {}
    ask_counts = dict(state.get("field_ask_count", {})) if state.get("field_ask_count") else {}
    chat_id = state["chat_id"]
    
    print(f"📦 Current experience: {experience}")
    print(f"📦 Field completion: {completion}")
    print(f"📦 Current field: {state.get('current_field')}")
    
    # ============================================================
    # STEP 0: Handle Edit Mode
    # ============================================================
    if state.get("awaiting_field_to_edit"):
        print("➡️ Handling edit request...")
        field_to_edit = None
        for field in ALL_FIELDS:
            if field in latest_msg_clean.replace(" ", "_"):
                field_to_edit = field
                break
        
        if "submit" in latest_msg_clean or "done" in latest_msg_clean or "looks good" in latest_msg_clean:
            print("✅ User is done editing. Re-confirming...")
            title = experience.get('title', 'Untitled Experience')
            summary = format_experience_summary(experience)
            msg_content = f"Excellent! Here's the updated summary for **{title}**:\n"
            msg_content += summary
            msg_content += "\n\n**Does everything look correct now?** (Please respond 'yes' or 'no')."
            msg = send_experience_message(chat_id, msg_content)
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
                "awaiting_field_to_edit": False,
                "awaiting_confirmation": True,
                "current_field": None,
            }

        if field_to_edit:
            print(f"✏️ User wants to edit field: {field_to_edit}")
            completion[field_to_edit] = False
            ask_counts[field_to_edit] = 0
            
            q = generate_experience_question_with_agent(field_to_edit, state["messages"], experience, 1)
            msg = send_experience_message(chat_id, f"Sure, let's update the **{field_to_edit.replace('_', ' ')}**. {q.question}")
            
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
                "field_completion_status": completion,
                "field_ask_count": ask_counts,
                "current_field": field_to_edit,
                "awaiting_field_to_edit": False,
                "interaction_count": state.get("interaction_count", 0) + 1,
            }
        else:
            print("⚠️ Unclear edit request. Re-asking.")
            msg = send_experience_message(chat_id, "I'm not sure which field you'd like to edit. Could you specify? (e.g., 'title', 'tools', 'timeline'). Or just say 'submit' if everything looks good.")
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
            }

    # ============================================================
    # STEP 1: Handle Confirmation Reply
    # ============================================================
    if state.get("awaiting_confirmation"):
        print("➡️ Handling final confirmation...")
        if any(w in latest_msg_clean for w in CONFIRM_YES):
            save_success = save_experience_to_db(chat_id, experience)
            if save_success:
                print("✅ User confirmed. Experience saved successfully.")
                msg = send_experience_message(chat_id, "Perfect! Your experience has been submitted successfully. Thanks for sharing! 👋")
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
                "experiences_collected": [experience],
                "awaiting_confirmation": False,
                "current_field": None,
                "is_complete": True,
            }
        
        
        elif any(w in latest_msg_clean for w in CONFIRM_NO):
            print("❌ User rejected summary. Entering edit mode.")
            msg = send_experience_message(chat_id, "No problem! **Which field would you like to update?** (e.g., 'title', 'tools', 'timeline').\n\nOnce you're satisfied with the changes, just say 'submit'.")
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
                "awaiting_confirmation": False,
                "awaiting_field_to_edit": True,
                "current_field": None,
                "is_complete": False,
            }
        else:
            print("⚠️ Unclear confirmation. Re-asking.")
            msg = send_experience_message(chat_id, "I didn't quite catch that. Is the experience information correct and ready to submit? (Please respond 'yes' or 'no').")
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
            }

    # ============================================================
    # STEP 2: Get CURRENT field
    # ============================================================
    current_field_being_asked = state.get("current_field")
    if not current_field_being_asked:
        current_field_being_asked = get_next_experience_field_to_collect(completion)

    if not current_field_being_asked:
        print("✅ Experience already completed. No more fields.")
        msg = send_experience_message(chat_id, "It looks like we've already collected all your experience information! If you need to make changes, please let me know.")
        return {
            **state,
            "messages": state["messages"] + [msg],
            "current_experience": experience,
        }

    print(f"🎯 CURRENT FIELD TO PROCESS: {current_field_being_asked}")

    # ============================================================
    # STEP 3: ✨ CLASSIFY USER INTENT (NEW - LLM-BASED)
    # ============================================================
    intent = classify_user_intent_experience(
        user_message=latest_msg_content,
        current_field=current_field_being_asked,
        conversation_history=state["messages"],
        experience_data=experience
    )
    
    # ============================================================
    # STEP 4: Handle SUMMARY request (LLM detected)
    # ============================================================
    if intent.intent == "request_summary":
        print("➡️ User requested summary (LLM-detected)")
        summary = "Of course! Here's what we have so far:"
        if experience:
            summary += format_experience_summary(experience)
        else:
            summary = "We haven't captured any experience details yet!"
        
        q = generate_experience_question_with_agent(current_field_being_asked, state["messages"], experience, ask_counts.get(current_field_being_asked, 0))
        summary += f"\n\nNow, let's continue: {q.question}"
        
        msg = send_experience_message(chat_id, summary)
        
        return {
            **state,
            "messages": state["messages"] + [msg],
            "current_experience": experience,
            "field_completion_status": completion,
            "field_ask_count": ask_counts,
            "current_field": current_field_being_asked,
            "interaction_count": state.get("interaction_count", 0) + 1,
        }

    # ============================================================
    # STEP 5: Handle CLARIFICATION request (LLM detected & generated)
    # ============================================================
    if intent.intent == "request_clarification":
        print(f"➡️ User needs clarification (LLM-detected)")
        print(f"   Topic: {intent.clarification_topic}")
        
        # Generate contextual clarification using LLM
        clarification = generate_clarification_response_experience(
            user_message=latest_msg_content,
            current_field=current_field_being_asked,
            clarification_topic=intent.clarification_topic,
            conversation_history=state["messages"],
            experience_data=experience
        )
        
        # Build response
        response_parts = [clarification.explanation]
        
        if clarification.example:
            response_parts.append(f"\n\n**For example:** {clarification.example}")
        
        response_parts.append(f"\n\n{clarification.follow_up_question}")
        
        response = "".join(response_parts)
        msg = send_experience_message(chat_id, response)
        
        return {
            **state,
            "messages": state["messages"] + [msg],
            "current_experience": experience,
            "field_completion_status": completion,
            "field_ask_count": ask_counts,
            "current_field": current_field_being_asked,
            "interaction_count": state.get("interaction_count", 0) + 1,
        }

    # ============================================================
    # STEP 6: Handle DONE request (LLM detected)
    # ============================================================
    if intent.intent == "request_done":
        print("➡️ User wants to finish (LLM-detected)")
        summary_msg = "Understood. I'll stop collecting information for this experience. "
        if experience.get("title"):
            summary_msg += "Since we haven't captured everything, I won't save this one. Feel free to start again anytime!"
        else:
            summary_msg = "Alright, no experience has been captured yet. Let me know if you'd like to start!"
        
        msg = send_experience_message(chat_id, summary_msg)
        return {
            **state,
            "messages": state["messages"] + [msg],
            "current_experience": experience,
            "current_field": None
        }

    # ============================================================
    # STEP 7: Handle SKIP (explicit keyword check)
    # ============================================================
    if latest_msg_clean in SKIP_PHRASES:
        print(f"➡️ User explicitly skipped field: {current_field_being_asked}")
        completion[current_field_being_asked] = True 
        
        next_field = get_next_experience_field_to_collect(completion)
        if not next_field:
            print("✅ All fields complete (last one skipped)! Moving to confirmation.")
            title = experience.get('title', 'Untitled Experience')
            summary = format_experience_summary(experience)
            msg_content = f"No worries! It looks like we have all the information now. Here's the summary for **{title}**:\n"
            msg_content += summary
            msg_content += "\n\n**Does this look accurate?** (Please respond 'yes' or 'no')."
            msg = send_experience_message(chat_id, msg_content)
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
                "field_completion_status": completion,
                "current_field": None, 
                "awaiting_confirmation": True,
                "interaction_count": state.get("interaction_count", 0) + 1,
            }

        print(f"⏭️ Skipping to next field: {next_field}")
        ask_counts[next_field] = 1
        q = generate_experience_question_with_agent(next_field, state["messages"], experience, 1)
        
        ack = f"That's fine, we can skip {current_field_being_asked.replace('_', ' ')}. "
        msg = send_experience_message(chat_id, f"{ack}{q.question}")
        
        return {
            **state,
            "messages": state["messages"] + [msg],
            "current_experience": experience,
            "field_completion_status": completion,
            "field_ask_count": ask_counts,
            "current_field": next_field,
            "interaction_count": state.get("interaction_count", 0) + 1,
        }

    # ============================================================
    # STEP 8: Extract data for CURRENT field (answer_question intent)
    # ============================================================
    if intent.intent == "answer_question":
        print(f"🔬 Extracting {current_field_being_asked}...")
        res = extract_experience_field_with_agent(current_field_being_asked, state["messages"], experience.get(current_field_being_asked))
        
        is_now_complete = False
        
        if is_field_data_present(res.extracted_value):
            if current_field_being_asked in ['tools_and_technologies', 'role_and_responsibilities', 'outcomes_or_achievements', 'skills_gained'] and isinstance(res.extracted_value, list):
                current_list = experience.get(current_field_being_asked, [])
                new_items = [item for item in res.extracted_value if item not in current_list]
                experience[current_field_being_asked] = current_list + new_items
            else:
                experience[current_field_being_asked] = res.extracted_value
            print(f"✅ Saved {current_field_being_asked}: {experience[current_field_being_asked]}")
        
        if res.is_complete and res.confidence > 0.5:
            is_now_complete = True
            if not is_field_data_present(res.extracted_value):
                print(f"✅ {current_field_being_asked} marked COMPLETE (user provided no data)")
        elif is_field_data_present(res.extracted_value):
            is_now_complete = True
            print(f"✅ {current_field_being_asked} marked COMPLETE (data extracted)")
        
        # ============================================================
        # STEP 9: Decide What's Next
        # ============================================================
        if is_now_complete:
            completion[current_field_being_asked] = True
            print(f"✅ {current_field_being_asked} marked COMPLETE")
            
            next_field = get_next_experience_field_to_collect(completion)
            
            if not next_field:
                print("✅ All fields complete! Moving to confirmation.")
                title = experience.get('title', 'Untitled Experience')
                summary = format_experience_summary(experience)
                
                msg_content = f"Excellent! I believe I have all the information for **{title}**. Here's a complete summary:\n"
                msg_content += summary
                msg_content += "\n\n**Does everything look correct?** (Please respond 'yes' or 'no')."
                
                msg = send_experience_message(chat_id, msg_content)
                
                return {
                    **state,
                    "messages": state["messages"] + [msg],
                    "current_experience": experience,
                    "field_completion_status": completion,
                    "current_field": None, 
                    "awaiting_confirmation": True,
                    "interaction_count": state.get("interaction_count", 0) + 1,
                }
            
            print(f"➡️ Moving to next field: {next_field}")
            new_ask_count = 1
            ask_counts[next_field] = new_ask_count
            q = generate_experience_question_with_agent(next_field, state["messages"], experience, new_ask_count)
            
            ack = get_random_experience_acknowledgment(current_field_being_asked)
            msg = send_experience_message(chat_id, f"{ack} {q.question}")
            
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
                "field_completion_status": completion,
                "field_ask_count": ask_counts,
                "current_field": next_field,
                "interaction_count": state.get("interaction_count", 0) + 1,
            }

        else:
            print(f"⚠️ {current_field_being_asked} is NOT complete.")
            ask_count = ask_counts.get(current_field_being_asked, 0)
            max_asks = 2 if current_field_being_asked in MANDATORY_FIELDS else 1
            
            if ask_count >= max_asks:
                print(f"⏭️ Skipping {current_field_being_asked} (max asks reached)")
                completion[current_field_being_asked] = True
                
                next_field_after_skip = get_next_experience_field_to_collect(completion)
                if not next_field_after_skip:
                    print("✅ All fields complete (last one skipped via max_asks)!")
                    title = experience.get('title', 'Untitled Experience')
                    summary = format_experience_summary(experience)
                    msg_content = f"That's alright. I think we have everything for **{title}**. Here's the summary:\n"
                    msg_content += summary
                    msg_content += "\n\n**Does this look accurate?** (Please respond 'yes' or 'no')."
                    msg = send_experience_message(chat_id, msg_content)
                    return {
                        **state,
                        "messages": state["messages"] + [msg],
                        "current_experience": experience,
                        "field_completion_status": completion,
                        "current_field": None, 
                        "awaiting_confirmation": True,
                        "interaction_count": state.get("interaction_count", 0) + 1,
                    }

                print(f"➡️ Moving to next field after skip: {next_field_after_skip}")
                new_ask_count = 1
                ask_counts[next_field_after_skip] = new_ask_count
                q = generate_experience_question_with_agent(next_field_after_skip, state["messages"], experience, new_ask_count)
                
                ack = f"No problem, let's move on from {current_field_being_asked.replace('_', ' ')}. "
                msg = send_experience_message(chat_id, f"{ack}{q.question}")
                
                return {
                    **state,
                    "messages": state["messages"] + [msg],
                    "current_experience": experience,
                    "field_completion_status": completion,
                    "field_ask_count": ask_counts,
                    "current_field": next_field_after_skip,
                    "interaction_count": state.get("interaction_count", 0) + 1,
                }
            
            new_ask_count = ask_count + 1
            ask_counts[current_field_being_asked] = new_ask_count
            
            print(f"💬 Re-asking for {current_field_being_asked} (attempt {new_ask_count}/{max_asks})")
            q = generate_experience_question_with_agent(current_field_being_asked, state["messages"], experience, new_ask_count)
            
            re_ask_intro = get_re_ask_phrase(new_ask_count)
            msg = send_experience_message(chat_id, f"{re_ask_intro} {q.question}")
            
            return {
                **state,
                "messages": state["messages"] + [msg],
                "current_experience": experience,
                "field_completion_status": completion,
                "field_ask_count": ask_counts,
                "current_field": current_field_being_asked,
                "interaction_count": state.get("interaction_count", 0) + 1,
            }
    
    # ============================================================
    # STEP 10: Handle OFF_TOPIC or unclassified intents
    # ============================================================
    else:
        print(f"⚠️ Intent classified as: {intent.intent}")
        q = generate_experience_question_with_agent(current_field_being_asked, state["messages"], experience, ask_counts.get(current_field_being_asked, 0))
        
        response = "I appreciate you sharing that! However, I'm specifically focused on collecting information about your professional experience right now. "
        response += q.question
        
        msg = send_experience_message(chat_id, response)
        
        return {
            **state,
            "messages": state["messages"] + [msg],
            "current_experience": experience,
            "field_completion_status": completion,
            "field_ask_count": ask_counts,
            "current_field": current_field_being_asked,
            "interaction_count": state.get("interaction_count", 0) + 1,
        }

# ============================================================
# ✅ BUILD GRAPH (FOR EXPERIENCE)
# ============================================================
def build_experience_agent():
    graph = StateGraph(ExperienceGraphState)
    graph.add_node("start", start_experience_node)
    graph.add_node("process", process_experience_input_node)
    graph.add_conditional_edges("__start__", lambda s: "start" if s.get("is_first_message", True) else "process")
    graph.add_edge("start", END)
    graph.add_edge("process", END)
    checkpointer = MongoDBCustomCheckpointer(db.client)
    app = graph.compile(checkpointer=checkpointer)
    print("✅ EXPERIENCE GRAPH COMPILED - LLM-BASED INTENT CLASSIFICATION V5.0")
    return app

# ============================================================
# ✅ MESSAGE HANDLER (UPDATED FOR EXPERIENCE)
# ============================================================
def handle_experience_message(chat_id: str, user_message: str, app, api_key: str = None) -> dict:
    """
    Main entry point for handling a user's message.
    Now supports dynamic LLM initialization with API key from frontend.
    """
    config = {"configurable": {"thread_id": chat_id}, "recursion_limit": 10}
    db.append_message(chat_id, "user", user_message, "experiences")

    print(f"\n{'='*60}")
    print(f"📨 User message: {user_message} (Thread: {chat_id})")
    print(f"{'='*60}")

    try:
        # ✅ Dynamic LLM + agent setup per request
        llm = get_llm(api_key)
        print(f"🤖 LLM initialized for request with API key: {'Provided' if api_key else 'Default'}")
        globals()['EXPERIENCE_FIELD_EXTRACTOR_AGENTS'], globals()['EXPERIENCE_FIELD_QUESTION_AGENTS'], globals()['EXPERIENCE_INTENT_CLASSIFIER'], globals()['EXPERIENCE_CLARIFICATION_GENERATOR'] = init_experience_agents_with_llm(llm)

        input_state = {"messages": [HumanMessage(content=user_message)]}
        result = app.invoke(input_state, config)
        final_state = app.get_state(config)
        final_values = final_state.values if final_state and final_state.values else {}

        if final_values:
            print(f"📦 State AFTER invoke:")
            print(f"   - current_experience: {final_values.get('current_experience', {})}")
            print(f"   - current_field: {final_values.get('current_field')}")
            print(f"   - field_completion_status: {final_values.get('field_completion_status', {})}")
            print(f"   - is_complete: {final_values.get('is_complete', False)}")

        ai_msgs = [m for m in final_values.get("messages", []) if isinstance(m, AIMessage)]
        ai_response = ai_msgs[-1].content if ai_msgs else "I'm not sure what to say. Could you tell me about your experience?"

        status_dict = final_values.get("field_completion_status", {f: False for f in ALL_FIELDS})
        completed_fields = sum(1 for v in status_dict.values() if v is True)
        total_fields = len(ALL_FIELDS)
        percentage = int((completed_fields / total_fields) * 100) if total_fields > 0 else 0
        is_experience_complete = final_values.get("is_complete", False)

        if not is_experience_complete and "experience has been submitted successfully" in ai_response:
            status_dict = {f: True for f in ALL_FIELDS}
            percentage = 100
            is_experience_complete = True

        return_data = {
            "chat_id": chat_id,
            "ai_response": ai_response,
            "current_section": "experiences",
            "is_complete": is_experience_complete,
            "percentage": percentage,
            "status": status_dict
        }

        print(f"\n🤖 AI Response: {ai_response}")
        print(f"✅ Returning data: {return_data}")
        return return_data

    except Exception as e:
        print(f"❌ Error during graph invocation: {e}")
        import traceback
        traceback.print_exc()

        error_msg = "I encountered an error. Could you try again?"
        db.append_message(chat_id, "ai", error_msg, "experiences")

        status_dict = {f: False for f in ALL_FIELDS}
        percentage = 0
        is_complete = False 
        try:
            current_state = app.get_state(config)
            if current_state and current_state.values:
                status_dict = current_state.values.get("field_completion_status", status_dict)
                is_complete = current_state.values.get("is_complete", False)
                completed_fields = sum(1 for v in status_dict.values() if v is True)
                total_fields = len(ALL_FIELDS)
                if total_fields > 0:
                    percentage = int((completed_fields / total_fields) * 100)
        except Exception as se:
            print(f"Could not retrieve state during error: {se}")

        return {
            "chat_id": chat_id,
            "ai_response": error_msg,
            "current_section": "experiences",
            "is_complete": is_complete, 
            "percentage": percentage,
            "status": status_dict
        }

# ============================================================
# ✅ EXPORT
# ============================================================
langgraph_experience_app = build_experience_agent()