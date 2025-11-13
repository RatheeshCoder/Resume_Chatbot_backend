# src/services/project_resume.py

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError, validator
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq
from src.config import settings


# ============================================================
# ✅ Pydantic Schema (Simplified)
# ============================================================
class ATSProject(BaseModel):
    title: str
    role: str
    team_size: Optional[int] = None
    timeline: Dict[str, str]
    type: str
    description: List[str]  # Changed to List - contains all details
    links: Optional[Dict[str, str]] = None

# ============================================================
# 🚀 ANTI-HALLUCINATION PROMPT (Unified Description)
# ============================================================
prompt = PromptTemplate.from_template("""
You are an **expert FAANG resume writer and ATS optimization specialist**.  
Your task: Convert the raw project data into a **fully valid JSON** object following the schema below.

🚨 **CRITICAL ANTI-HALLUCINATION RULES** 🚨
1. **USE ONLY THE PROVIDED DATA** - Do NOT invent, assume, or add information not explicitly present in the raw data
2. **NO FABRICATION** - If a field is missing or unclear in the raw data, use null or omit it
3. **EXACT ROLE EXTRACTION** - The "role" field must be the user's actual role/position (e.g., "Full-Stack Developer", "Backend Engineer", "Solo Developer"), NOT a description of what they did
4. **LINKS POLICY** - If no links are provided in raw data, set links to null or empty object. NEVER use placeholder URLs like "https://github.com"
5. **UNIFIED DESCRIPTION** - Combine tech_stack, description, responsibilities, and outcome into a single "description" array with 4-6 bullet points

🧱 **JSON Schema**
{{
  "title": "string (extract from raw data)",
  "role": "string (user's actual role: e.g., 'Full-Stack Developer', 'Backend Engineer', 'Team Lead')",
  "team_size": number or null,
  "timeline": {{"start_date": "Month Year", "end_date": "Month Year"}},
  "type": "string (personal/academic/professional/hackathon)",
  "description": [
    "Bullet point 1: What the project does + main tech stack used",
    "Bullet point 2: Technical approach/architecture with specific technologies",
    "Bullet point 3: Key implementation details or features built",
    "Bullet point 4: Additional technical responsibilities or methodology",
    "Bullet point 5 (optional): Results/outcome with metrics if available",
    "Bullet point 6 (optional): Additional achievements or impact"
  ],
  "links": {{"github": "url", "live_demo": "url"}} or null
}}

⚙️ **Description Array Rules** (MOST IMPORTANT):

**Structure of "description" array:**
1. **First bullet**: Project overview + primary technologies
   - Format: "Action verb + what project does + using [Tech1, Tech2, Tech3]"
   - Example: "Developed a real-time fitness tracking application using React, Node.js, MongoDB, and AWS"
   
2. **Second bullet**: Technical architecture/approach + specific tools
   - Format: "Action verb + technical approach + with [specific technologies]"
   - Example: "Implemented RESTful API architecture with Express.js backend and JWT authentication"
   
3. **Third bullet**: Key features or implementation details
   - Format: "Action verb + feature/functionality + technology used"
   - Example: "Built responsive component-based UI with React Hooks and Material-UI for seamless user experience"
   
4. **Fourth bullet**: Additional technical work or methodology
   - Format: "Action verb + technical detail + technology/pattern"
   - Example: "Integrated third-party APIs for workout data synchronization using Axios and async/await patterns"
   
5. **Fifth bullet (if outcome exists)**: Results with metrics
   - Format: "Action verb + achievement + quantifiable metric"
   - Example: "Achieved 2,000+ active users within first month with 95% positive feedback rating"
   
6. **Sixth bullet (optional)**: Additional impact or technical achievement
   - Format: "Action verb + additional impact"
   - Example: "Optimized database queries reducing response time by 40% and improving scalability"

**ATS Keyword Strategy:**
- **Embed ALL technologies** from "tools" field naturally into bullets
- **Use power action verbs**: Developed, Engineered, Designed, Implemented, Built, Created, Architected, Integrated, Optimized, Deployed, Automated, Configured
- **Include technical terms**: API, database, frontend, backend, cloud, CI/CD, microservices, authentication, deployment, testing, optimization, scalability, performance
- **Add methodology keywords**: Agile, Git, version control, debugging, testing, documentation, code review
- **Quantify when possible**: Use numbers, percentages, metrics from "outcome" field
- **Be specific**: Name exact technologies, frameworks, libraries, patterns used

**Role Extraction Examples:**
- If raw says "I was the full-stack developer" → role: "Full-Stack Developer"
- If raw says "I handled backend" → role: "Backend Developer"
- If raw says "Solo project" → role: "Solo Developer"
- If raw says "Led a team of 4" → role: "Team Lead"
- If raw says "Frontend work" → role: "Frontend Developer"

**CRITICAL**: 
- NO MARKDOWN in output (no ```json``` blocks)
- Every bullet MUST include specific technology names from the "tools" field
- Bullets should flow logically: overview → architecture → features → implementation → results
- Length: Each bullet should be 10-20 words for optimal ATS parsing

🔍 **Validation Checklist Before Output**:
- [ ] Role is a job title, not a task description
- [ ] Description array has 4-6 bullets
- [ ] ALL tools from raw data are mentioned in description bullets
- [ ] Each bullet starts with a power action verb
- [ ] Outcome/metrics included if provided in raw data
- [ ] Links are real URLs from raw data or null
- [ ] No invented information - everything traceable to raw input

---

**RAW PROJECT DATA:**
{raw_project}

**INSTRUCTIONS:**
1. Read the raw data carefully
2. Identify all technologies in the "tools" field
3. Create 4-6 description bullets that incorporate:
   - What the project does ("what" field)
   - How it was built ("how" field)
   - Technologies used ("tools" field) - MUST be in bullets
   - Outcome/results ("outcome" field) if available
4. Extract proper role from "role" field
5. Handle links properly (null if empty)
6. Output ONLY valid JSON (no markdown, no explanations)

**OUTPUT:**
""")


# ============================================================
# 🧹 JSON Extraction Utility
# ============================================================
def extract_clean_json(text: str) -> dict:
    """
    Cleans LLM output and extracts the first valid JSON block.
    """
    try:
        # Remove markdown or code fences
        text = re.sub(r"```(?:json)?", "", text)
        text = re.sub(r"```", "", text)
        text = text.strip()

        # Extract JSON between first { and last }
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        # Try to load JSON safely
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"❌ Failed to parse JSON: {e}\nRaw text:\n{text}")

# ============================================================
# 🛡️ POST-PROCESSING: Anti-Hallucination Validation
# ============================================================
def validate_and_fix_hallucinations(
    generated_json: Dict[str, Any], 
    raw_project: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validates LLM output against raw input to prevent hallucinations.
    Fixes common issues like wrong roles, fake links, and invented data.
    """
    print("🛡️ Running anti-hallucination validation...")
    
    # 1️⃣ Fix Links - Remove placeholder URLs
    if "links" in generated_json:
        links = generated_json["links"]
        raw_links = raw_project.get("links", [])
        
        # Handle empty or placeholder links
        if not raw_links or raw_links == [] or raw_links == [""]:
            generated_json["links"] = None
        elif isinstance(links, dict):
            # Check for placeholder URLs
            github = links.get("github", "")
            live_demo = links.get("live_demo", "")
            
            # Remove if placeholder
            if github and ("github.com" == github or "https://github.com" == github):
                github = None
            if live_demo and ("github.com" == live_demo or "https://github.com" == live_demo):
                live_demo = None
            
            # Extract real links from raw data
            if isinstance(raw_links, list) and raw_links:
                actual_links = [l for l in raw_links if l and isinstance(l, str) and l.strip()]
                if actual_links:
                    github_link = next((l for l in actual_links if "github" in l.lower()), None)
                    other_links = [l for l in actual_links if "github" not in l.lower()]
                    live_link = other_links[0] if other_links else None
                    
                    generated_json["links"] = {}
                    if github_link:
                        generated_json["links"]["github"] = github_link
                    if live_link:
                        generated_json["links"]["live_demo"] = live_link
                    
                    if not generated_json["links"]:
                        generated_json["links"] = None
                else:
                    generated_json["links"] = None
            else:
                generated_json["links"] = None
    
    # 2️⃣ Validate Role - Must be a job title, not a description
    if "role" in generated_json:
        role = generated_json["role"]
        raw_role = raw_project.get("role", "")
        
        # Check if role is too long (likely a description, not a title)
        if len(role) > 50:
            # Try to extract actual role from raw data
            if raw_role and len(raw_role) < 50:
                generated_json["role"] = raw_role
            else:
                # Fallback: infer from context
                if raw_project.get("team_size") == 1:
                    generated_json["role"] = "Solo Developer"
                else:
                    generated_json["role"] = "Developer"
            print(f"⚠️ Fixed overly long role: {role[:50]}... → {generated_json['role']}")
        
        # Use raw role if available and reasonable
        elif raw_role and len(raw_role) < 50:
            generated_json["role"] = raw_role
    
    # 3️⃣ Validate Description Array - Must mention all tools
    if "description" in generated_json and isinstance(generated_json["description"], list):
        raw_tools = raw_project.get("tools", [])
        if isinstance(raw_tools, list) and raw_tools:
            # Check if all tools are mentioned somewhere in the description bullets
            description_text = " ".join(generated_json["description"]).lower()
            missing_tools = []
            
            for tool in raw_tools:
                if isinstance(tool, str) and tool.lower() not in description_text:
                    missing_tools.append(tool)
            
            # If tools are missing, try to add them to the first bullet
            if missing_tools:
                print(f"⚠️ Missing tools in description: {missing_tools}")
                # Add missing tools to first bullet if possible
                if generated_json["description"]:
                    first_bullet = generated_json["description"][0]
                    # Append missing tools
                    tools_str = ", ".join(missing_tools)
                    if "using" in first_bullet.lower():
                        # Insert before existing tools
                        generated_json["description"][0] = first_bullet.replace(
                            " using ", f" using {tools_str}, "
                        )
                    else:
                        # Append at end
                        generated_json["description"][0] = f"{first_bullet.rstrip('.')} using {tools_str}"
    
    # 4️⃣ Validate Outcome - Must be from raw data
    if "outcome" in raw_project and raw_project["outcome"]:
        raw_outcome = raw_project["outcome"]
        # Check if outcome is mentioned in any description bullet
        if "description" in generated_json and isinstance(generated_json["description"], list):
            description_text = " ".join(generated_json["description"]).lower()
            outcome_keywords = raw_outcome.lower().split()
            
            # Check if at least some outcome keywords are present
            outcome_mentioned = any(keyword in description_text for keyword in outcome_keywords if len(keyword) > 3)
            
            if not outcome_mentioned and len(generated_json["description"]) < 6:
                # Add outcome as last bullet if not mentioned
                print(f"⚠️ Adding missing outcome to description")
                generated_json["description"].append(f"Achieved {raw_outcome}")
    
    # 5️⃣ Handle Optional Fields
    if "team_size" in generated_json:
        if generated_json["team_size"] == 0 or not raw_project.get("team_size"):
            generated_json["team_size"] = None
    
    print("✅ Validation complete")
    return generated_json

# ============================================================
# 🎯 Main Function
# ============================================================
def format_ats_project_with_llm(project: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """
    Generates a clean, validated ATS-optimized JSON object from raw project data.
    Includes anti-hallucination checks.
    Now outputs unified description array with all details.
    """
    print("⚙️ Processing project with advanced ATS formatter...")
    print(f"📥 Input data: {json.dumps(project, indent=2)}\n")

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=api_key,
        temperature=0.0,  # More deterministic
        max_tokens=2000   # Reduced to encourage concise output
    )
    chain = prompt | llm

    # 1️⃣ Invoke LLM (returns AIMessage)
    ai_message = chain.invoke({"raw_project": json.dumps(project, indent=2)})

    # 2️⃣ Extract content safely
    llm_output = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
    print("\n[LLM RAW OUTPUT]\n", llm_output[:800], "...\n")

    # 3️⃣ Extract and clean JSON
    clean_json = extract_clean_json(llm_output)
    print(f"🧹 Cleaned JSON: {json.dumps(clean_json, indent=2)}\n")

    # 4️⃣ **CRITICAL**: Run anti-hallucination validation
    validated_json = validate_and_fix_hallucinations(clean_json, project)
    print(f"🛡️ Validated JSON: {json.dumps(validated_json, indent=2)}\n")

    # 5️⃣ Validate with Pydantic schema
    try:
        ats_data = ATSProject(**validated_json)
        final_json = ats_data.model_dump()
    except ValidationError as e:
        print(f"❌ Pydantic validation error: {e}")
        # Attempt to fix and retry
        final_json = validated_json

    print("✅ SUCCESS: Valid ATS-optimized JSON generated.")
    print(f"📤 Final output: {json.dumps(final_json, indent=2)}")
    return final_json
