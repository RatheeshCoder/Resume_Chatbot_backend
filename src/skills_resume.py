# src/services/skills_resume.py
import json
import re
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, ValidationError
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from src.config import settings


# ============================================================
# Pydantic Schema for Skills Section
# ============================================================
class ATSSkillsSection(BaseModel):
    category_name: str = Field(
        description="The skill domain/category name (e.g., 'Frontend Development', 'Full Stack Web Development')"
    )
    skills: List[str] = Field(
        description="List of all unique skills under this category in ATS-optimized format"
    )
    keyword_density_score: Optional[int] = Field(
        default=None,
        description="Estimated ATS keyword match score (1-10)"
    )


# ============================================================
# ADVANCED ATS SKILLS EXTRACTION PROMPT
# ============================================================
prompt = PromptTemplate.from_template("""
You are an **elite ATS resume strategist and full-stack career optimizer** with 15+ years of experience helping candidates land roles at FAANG companies and top-tier tech firms.

Your mission: Transform raw student skills data into a **highly effective, ATS-optimized Skills section** that:
- Maximizes keyword matching for Applicant Tracking Systems
- Is categorized cleanly for both ATS parsing and human readability
- Extracts ALL possible relevant skills from the input data
- Follows industry-standard naming conventions
- Is formatted for plain-text resume compatibility

---

## OUTPUT JSON SCHEMA

{{
  "category_name": "Full Stack Web Development",
  "skills": ["React", "Node.js", "MongoDB", "Express.js", "HTML5", "CSS3", "JavaScript (ES6+)", "Redux", "Tailwind CSS", "JWT Authentication", "API Integration", "Git", "Docker", "Agile", "Problem-Solving", ...],
  "keyword_density_score": 8
}}

**CRITICAL**: The "category_name" should be taken from the "skill_domain" field in the raw input data.

---

## SKILL EXTRACTION STRATEGY

### PRIMARY SOURCES (Extract from ALL fields):
1. **skills_list** - Direct technical skills mentioned
2. **tools_or_frameworks** - All tools, frameworks, libraries, technologies
3. **how_skills_were_used** - Extract technical terms (MERN, API, responsive UI, etc.)
4. **projects_using_this_skill** - Project context may reveal additional skills
5. **key_achievements_using_this_skill** - Technical terms in achievements (MongoDB queries, API optimization, UI/UX, etc.)
6. **practical_application_example** - Real-world usage often mentions additional tools
7. **learning_sources** - May reference specific platforms or methodologies
8. **skill_domain** - High-level category that may contain extractable keywords

### SKILL INFERENCE RULES:
- If "MERN stack" mentioned → Extract: MongoDB, Express.js, React, Node.js
- If "Full Stack" mentioned → Include both frontend and backend categories
- If "responsive UI" mentioned → Include: Responsive Design, CSS3, HTML5
- If "API integration" mentioned → Include: REST APIs, API Development
- If "authentication" mentioned → Include: JWT, Authentication, Authorization
- If specific frameworks mentioned → Include the base language (e.g., React → JavaScript)

---

## CATEGORIZATION FRAMEWORK

**ALL skills will be in a SINGLE flat list** - No separate categories needed.

### Skills to Extract and Include:

**Frontend**: React, Angular, Vue, Next.js, HTML5, CSS3, SCSS, Sass, Tailwind CSS, Bootstrap, JavaScript (ES6+), TypeScript, jQuery, Redux, Context API, Webpack, Babel, Responsive Design, UI/UX Design, Figma

**Backend**: Node.js, Express.js, Django, Flask, Spring Boot, FastAPI, .NET, REST APIs, GraphQL, Microservices, WebSockets, Server-Side Rendering, API Development, API Integration

**Databases**: MongoDB, PostgreSQL, MySQL, Redis, SQLite, DynamoDB, Elasticsearch, Firebase, Prisma, Sequelize, Mongoose, Database Design, Query Optimization

**Tools**: Git, GitHub, GitLab, Bitbucket, VS Code, IntelliJ, Postman, Insomnia, Jira, Trello, Slack, Figma, Adobe XD, npm, Yarn, Webpack

**Cloud**: AWS, Azure, Google Cloud Platform (GCP), Docker, Kubernetes, Jenkins, CircleCI, GitHub Actions, CI/CD, Terraform, Nginx, Apache, Vercel, Netlify, Heroku

**Languages**: JavaScript, TypeScript, Python, Java, C++, C#, Go, PHP, Ruby, Swift, Kotlin

**Testing**: Jest, Mocha, Chai, Cypress, Selenium, React Testing Library, Unit Testing, Integration Testing, Test-Driven Development (TDD)

**Mobile** (if applicable): React Native, Flutter, Swift, Kotlin, Android, iOS, Mobile-First Design

**Data** (if applicable): Data Analysis, Data Visualization, Pandas, NumPy, Matplotlib, Tableau, Power BI, SQL, ETL

**Other**: Agile, Scrum, Problem-Solving, Communication, Version Control, Code Review, Performance Optimization, Security Best Practices, Accessibility (WCAG), SEO, Authentication (JWT, OAuth), State Management

---

## SKILL NAMING CONVENTIONS (CRITICAL FOR ATS)

**Use Industry-Standard Terms**:
- ✅ "JavaScript (ES6+)" NOT "JS" or "Javascript"
- ✅ "Node.js" NOT "NodeJS" or "Node"
- ✅ "MongoDB" NOT "Mongo" or "mongo db"
- ✅ "REST APIs" NOT "RESTful APIs" or "Rest api"
- ✅ "HTML5" and "CSS3" NOT "HTML" or "CSS"
- ✅ "React.js" or "React" (both acceptable)
- ✅ "Express.js" NOT "Express" alone
- ✅ "Tailwind CSS" NOT "TailwindCSS"
- ✅ "Git" and "GitHub" as separate items
- ✅ "JWT" or "JWT Authentication" (both work)
- ✅ "CI/CD" NOT "Continuous Integration"

**Capitalization Rules**:
- Proper nouns: MongoDB, JavaScript, PostgreSQL, GitHub
- Acronyms: API, REST, JWT, HTML5, CSS3, CI/CD, AWS, GCP
- Frameworks: React.js, Node.js, Express.js, Next.js

---

## EXTRACTION PROCESS (Step-by-Step)

### Step 1: Direct Extraction (HIGHEST PRIORITY)
- Extract ALL items from "skills_list" EXACTLY as written
- Extract ALL items from "tools_or_frameworks" EXACTLY as written
- These are your PRIMARY and MANDATORY skills

### Step 2: Text Mining (CAREFUL - Only explicit mentions)
- Scan "how_skills_were_used" for EXPLICITLY NAMED technologies
  - Example: "using MERN stack" → Extract: MongoDB, Express.js, React, Node.js
  - Example: "with API integration" → Extract: "API Integration"
  - ❌ Don't infer: "portfolio site" does NOT imply HTML/CSS unless stated
- Scan "key_achievements_using_this_skill" for EXPLICITLY NAMED technologies
  - Example: "optimized MongoDB queries" → Extract: MongoDB, Query Optimization
  - ❌ Don't infer: "improved performance" does NOT imply specific tools
- Scan "practical_application_example" for EXPLICITLY NAMED technologies
  - Example: "by optimizing MongoDB queries" → Extract: MongoDB
  - ❌ Don't add generic tools not mentioned

### Step 3: Domain Inference (VERY LIMITED)
- If "skill_domain" = "Full Stack Web Development" AND "MERN" mentioned → OK to expand MERN
- If "skill_domain" = "Frontend" → DO NOT add backend tools
- If "skill_domain" = "Backend" → DO NOT add frontend tools
- ❌ DO NOT infer tools from domain alone

### Step 4: Stack Expansion (ONLY if acronym mentioned)
- "MERN" mentioned → MongoDB, Express.js, React, Node.js
- "MEAN" mentioned → MongoDB, Express.js, Angular, Node.js
- "LAMP" mentioned → Linux, Apache, MySQL, PHP
- ❌ DO NOT expand if acronym not mentioned

### Step 5: Normalization (NOT Addition)
- "React" → "React" (keep as is)
- "NodeJS" → "Node.js" (normalize naming)
- "Javascript" → "JavaScript (ES6+)" (proper naming)
- "mongo" → "MongoDB" (proper naming)
- This step ONLY renames, does NOT add new skills

### Step 6: Deduplication
- Remove case-insensitive duplicates
- Merge similar terms (e.g., "React" and "React.js" → keep "React")

### Step 7: Final Validation
- Cross-check EVERY skill against source data
- Remove ANY skill that cannot be traced back
- Sort alphabetically

### Step 8: Keyword Density Score (Conservative)
- Calculate based ONLY on extracted skills (not potential skills)

---

## ANTI-HALLUCINATION RULES

**ABSOLUTE PROHIBITIONS - THIS IS CRITICAL**:
1. ❌ DO NOT add skills not present in input data
2. ❌ DO NOT infer skills from job titles without evidence
3. ❌ DO NOT add tools mentioned in examples but not in user data
4. ❌ DO NOT add soft skills unless explicitly mentioned
5. ❌ DO NOT add certifications or courses as skills
6. ❌ DO NOT duplicate skills across categories unnecessarily
7. ❌ DO NOT add "standard" tools like Git, GitHub, VS Code, Postman unless they appear in input
8. ❌ DO NOT add Docker, CI/CD, Vercel, npm unless mentioned in input
9. ❌ DO NOT expand beyond what's explicitly stated

**EXTRACTION SOURCES (ONLY extract from these)**:
- "skills_list" - Direct skills array
- "tools_or_frameworks" - Direct tools array
- "how_skills_were_used" - Extract ONLY explicitly mentioned technologies
- "key_achievements_using_this_skill" - Extract ONLY explicitly mentioned technologies
- "practical_application_example" - Extract ONLY explicitly mentioned technologies

**VALIDATION CHECKLIST**:
- [ ] Every skill must appear verbatim or clearly implied in input
- [ ] No invented technologies
- [ ] Proper capitalization and naming conventions
- [ ] No duplicate entries in "skills" list
- [ ] Skills are sorted alphabetically

**EXAMPLES OF WHAT TO EXTRACT vs NOT EXTRACT**:

✅ **CORRECT Extraction**:
Input: "tools_or_frameworks": ["React", "Node.js", "MongoDB"]
Output: ["React", "Node.js", "MongoDB"]

Input: "Developed using MERN stack"
Output: ["React", "Node.js", "Express.js", "MongoDB"]

Input: "built scalable APIs"
Output: ["API Development"] or ["REST APIs"] (generic term OK if APIs mentioned)

❌ **WRONG - Hallucination**:
Input: "tools_or_frameworks": ["React", "Node.js"]
Output: ["React", "Node.js", "Git", "VS Code", "npm"] ← Git, VS Code, npm NOT mentioned!

Input: "Developed a portfolio site"
Output: ["HTML5", "CSS3"] ← NOT mentioned explicitly!

Input: "Full Stack Web Development"
Output: [..., "Docker", "Kubernetes", "AWS"] ← NOT mentioned!

**STRICT RULE**: If a tool/technology is NOT explicitly mentioned in the input data, DO NOT include it. Period.

---

## OUTPUT REQUIREMENTS

1. **NO MARKDOWN** - Output pure JSON only (no ```json``` blocks)
2. **Minimum 10 skills** - Extract as many as possible from input
3. **Maximum 50 skills** - Too many dilutes keyword strength
4. **Single flat list** - All skills in one "skills" array
5. **Alphabetical sorting** - For clean, professional presentation
6. **Industry-standard naming** - Follow conventions above
7. **No duplicates** - Each skill appears only once

---

## EXAMPLE OUTPUT FORMAT

{{
  "category_name": "Full Stack Web Development",
  "skills": [
    "Agile", "API Integration", "CI/CD", "CSS3", "Docker", "Express.js", 
    "Git", "GitHub", "HTML5", "JavaScript (ES6+)", "JWT Authentication", 
    "MongoDB", "Node.js", "npm", "Performance Optimization", "Postman", 
    "Problem-Solving", "Query Optimization", "React", "Redux", 
    "Responsive Design", "REST APIs", "Tailwind CSS", "UI/UX Design", 
    "Vercel", "VS Code"
  ],
  "keyword_density_score": 8
}}

---

## CRITICAL OUTPUT INSTRUCTIONS

**YOU MUST OUTPUT ONLY THE FINAL JSON. NO EXPLANATIONS. NO STEP-BY-STEP WORK. NO MARKDOWN.**

❌ WRONG - Do NOT output like this:
```
Step 1: ...
Step 2: ...
{{"skills": [...]}}
```

✅ CORRECT - Output ONLY this:
```
{{"category_name": "Full Stack Web Development", "skills": [...], "keyword_density_score": 8}}
```

**ABSOLUTELY NO**:
- No step-by-step thinking
- No markdown code blocks (```json```)
- No explanations before or after JSON
- No intermediate outputs
- Just the raw JSON object, nothing else

---

**RAW SKILLS DATA:**
{raw_skills}

---

**YOUR TASK:**
1. Extract "category_name" directly from "skill_domain" field (e.g., "Full Stack Web Development")
2. Extract ALL possible skills from input data (skills_list, tools_or_frameworks, text fields)
3. Expand stack abbreviations (MERN → MongoDB, Express.js, React, Node.js)
4. Mine technical terms from descriptions and achievements
5. Apply proper naming conventions (JavaScript (ES6+), Node.js, etc.)
6. Remove duplicates and create single "skills" list
7. Sort alphabetically
8. Calculate keyword_density_score (1-10)
9. Validate - ensure every skill is traceable to input
10. **OUTPUT ONLY THE FINAL JSON - NO STEPS, NO MARKDOWN, NO EXPLANATIONS**

**CRITICAL**: Your response must be ONLY the JSON object. Start with {{ and end with }}. Nothing before, nothing after.

**OUTPUT (VALID JSON ONLY):**
""")


# ============================================================
# JSON Extraction Utility
# ============================================================
def extract_clean_json(text: str) -> dict:
    """
    Cleans LLM output and extracts the first valid JSON block.
    Handles cases where LLM outputs step-by-step work before the final JSON.
    """
    try:
        # Remove markdown code blocks
        text = re.sub(r"```(?:json)?", "", text)
        text = re.sub(r"```", "", text)
        text = text.strip()

        # Try to find the LAST complete JSON object (in case of multiple outputs)
        # Match from last { to last }
        matches = list(re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL))
        
        if matches:
            # Get the last (most likely final) JSON object
            last_match = matches[-1]
            json_text = last_match.group(0)
            
            # Try to parse it
            parsed = json.loads(json_text)
            
            # Ensure it has the expected structure
            if "skills" in parsed and isinstance(parsed["skills"], list):
                return parsed
            
            # If not valid, try other matches
            for match in reversed(matches[:-1]):
                json_text = match.group(0)
                try:
                    parsed = json.loads(json_text)
                    if "skills" in parsed and isinstance(parsed["skills"], list):
                        return parsed
                except:
                    continue
        
        # Fallback: try to parse the whole text
        return json.loads(text)
        
    except Exception as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw text:\n{text[:2000]}")


# ============================================================
# POST-PROCESSING: Validation & Deduplication
# ============================================================
def validate_skills_output(
    generated_json: Dict[str, Any],
    raw_skills: Dict[str, Any]
) -> Dict[str, Any]:
    """
    STRICT validation against hallucinations.
    Removes ANY skill not directly traceable to input data.
    """
    print("\n" + "="*60)
    print("ANTI-HALLUCINATION VALIDATION STARTING")
    print("="*60)

    # Ensure category_name is set from skill_domain
    if "skill_domain" in raw_skills and raw_skills["skill_domain"]:
        generated_json["category_name"] = raw_skills["skill_domain"]
    elif "category_name" not in generated_json:
        generated_json["category_name"] = "Technical Skills"

    # ===========================================================
    # STEP 1: Build whitelist of ALLOWED skills from input
    # ===========================================================
    allowed_skills = set()
    
    # Direct skills from lists (highest priority)
    if "skills_list" in raw_skills and isinstance(raw_skills["skills_list"], list):
        for skill in raw_skills["skills_list"]:
            if skill and isinstance(skill, str):
                allowed_skills.add(skill.strip().lower())
                print(f"✓ Allowed from skills_list: {skill}")
    
    if "tools_or_frameworks" in raw_skills and isinstance(raw_skills["tools_or_frameworks"], list):
        for tool in raw_skills["tools_or_frameworks"]:
            if tool and isinstance(tool, str):
                allowed_skills.add(tool.strip().lower())
                print(f"✓ Allowed from tools_or_frameworks: {tool}")

    # Text mining from descriptions (explicit mentions only)
    text_fields = {
        "how_skills_were_used": raw_skills.get("how_skills_were_used", ""),
        "practical_application_example": raw_skills.get("practical_application_example", ""),
        "key_achievements": " ".join(raw_skills.get("key_achievements_using_this_skill", [])),
    }
    
    # Common technology patterns to extract from text
    tech_patterns = [
        r'\bMERN\b', r'\bMEAN\b', r'\bLAMP\b',
        r'\bAPI\b', r'\bAPIs\b', r'\bREST\b', r'\bGraphQL\b',
        r'\bHTML\b', r'\bHTML5\b', r'\bCSS\b', r'\bCSS3\b',
        r'\bJavaScript\b', r'\bTypeScript\b', r'\bPython\b',
        r'\bresponsive\b', r'\bUI/UX\b', r'\bUI\b', r'\bUX\b',
        r'\bauthentication\b', r'\bJWT\b', r'\bOAuth\b',
        r'\bdatabase\b', r'\bqueries\b', r'\bquery optimization\b',
        r'\bperformance\b', r'\boptimization\b',
        r'\bagile\b', r'\bscrum\b'
    ]
    
    for field_name, text in text_fields.items():
        if text:
            text_lower = text.lower()
            # Check for MERN/MEAN stack
            if 'mern' in text_lower:
                for skill in ['mongodb', 'express', 'react', 'node.js']:
                    allowed_skills.add(skill)
                    print(f"✓ Allowed from MERN expansion in {field_name}: {skill}")
            
            if 'mean' in text_lower:
                for skill in ['mongodb', 'express', 'angular', 'node.js']:
                    allowed_skills.add(skill)
                    print(f"✓ Allowed from MEAN expansion in {field_name}: {skill}")
            
            # Extract other explicitly mentioned terms
            for pattern in tech_patterns:
                if re.search(pattern, text_lower):
                    match_text = re.search(pattern, text_lower).group(0)
                    allowed_skills.add(match_text.lower())
                    print(f"✓ Allowed from text pattern in {field_name}: {match_text}")

    # Generic skill terms that can be inferred
    if any('api' in str(v).lower() for v in text_fields.values()):
        allowed_skills.add('api integration')
        allowed_skills.add('api development')
        allowed_skills.add('rest apis')
        print("✓ Allowed API-related skills from context")
    
    if any('responsive' in str(v).lower() for v in text_fields.values()):
        allowed_skills.add('responsive design')
        print("✓ Allowed Responsive Design from context")
    
    if any('ui/ux' in str(v).lower() or 'ui' in str(v).lower() for v in text_fields.values()):
        allowed_skills.add('ui/ux design')
        print("✓ Allowed UI/UX Design from context")

    print(f"\n📋 Total allowed skills baseline: {len(allowed_skills)}")

    # ===========================================================
    # STEP 2: Filter generated skills against whitelist
    # ===========================================================
    if "skills" not in generated_json or not isinstance(generated_json["skills"], list):
        print("⚠️  No skills found in generated output")
        generated_json["skills"] = []
        return generated_json

    original_skills = generated_json["skills"].copy()
    validated_skills = []
    removed_skills = []

    for skill in original_skills:
        if not skill or not isinstance(skill, str):
            continue
            
        skill_lower = skill.lower().strip()
        
        # Check if skill is in allowed list (with fuzzy matching)
        is_allowed = False
        
        # Direct match
        if skill_lower in allowed_skills:
            is_allowed = True
        
        # Fuzzy match - check if any allowed skill is contained in this skill or vice versa
        for allowed in allowed_skills:
            # Normalize common variations
            skill_normalized = skill_lower.replace('.js', '').replace('js', '').strip()
            allowed_normalized = allowed.replace('.js', '').replace('js', '').strip()
            
            if (skill_normalized in allowed_normalized or 
                allowed_normalized in skill_normalized or
                skill_lower.startswith(allowed) or
                allowed.startswith(skill_lower)):
                is_allowed = True
                break
        
        if is_allowed:
            validated_skills.append(skill)
            print(f"✅ KEPT: {skill}")
        else:
            removed_skills.append(skill)
            print(f"❌ REMOVED (not in input): {skill}")

    # Update with validated skills
    generated_json["skills"] = sorted(list(set(validated_skills)))

    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY:")
    print(f"  Original count: {len(original_skills)}")
    print(f"  Validated count: {len(validated_skills)}")
    print(f"  Removed count: {len(removed_skills)}")
    if removed_skills:
        print(f"  Removed skills: {', '.join(removed_skills)}")
    print(f"{'='*60}\n")

    # Final warnings
    if len(generated_json["skills"]) < 3:
        print("⚠️  WARNING: Very few skills extracted (<3)")
    
    if len(generated_json["skills"]) > 40:
        print("⚠️  WARNING: Too many skills extracted (>40)")

    return generated_json


# ============================================================
# Main Function – Uses API key from header
# ============================================================
def format_ats_skills_with_llm(skills_data: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """
    Generates a clean, validated ATS-optimized skills section JSON.
    Uses the provided `api_key` from the `x-api-key` header.
    """
    print("Processing skills with advanced ATS formatter...")
    print(f"Input data: {json.dumps(skills_data, indent=2)}\n")

    # Create LLM instance with dynamic API key and stricter settings
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=api_key,
        temperature=0.0,  # More deterministic
        max_tokens=2000   # Reduced to encourage concise output
    )
    chain = prompt | llm

    # Invoke LLM
    ai_message = chain.invoke({"raw_skills": json.dumps(skills_data, indent=2)})
    llm_output = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
    print("\n[LLM RAW OUTPUT]\n", llm_output[:1000], "...\n")

    # Extract JSON
    clean_json = extract_clean_json(llm_output)
    print(f"Cleaned JSON: {json.dumps(clean_json, indent=2)}\n")

    # Validate
    validated_json = validate_skills_output(clean_json, skills_data)
    print(f"Validated JSON: {json.dumps(validated_json, indent=2)}\n")

    # Pydantic validation
    try:
        ats_data = ATSSkillsSection(**validated_json)
        final_json = ats_data.model_dump()
    except ValidationError as e:
        print(f"Pydantic validation error: {e}")
        final_json = validated_json

    print("SUCCESS: ATS-optimized skills section JSON generated.")
    print(f"Final output: {json.dumps(final_json, indent=2)}")
    return final_json