# src/services/achievement_resume.py
import json
import re
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, ValidationError
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from src.config import settings


# ============================================================
# Pydantic Schema for Achievement
# ============================================================
class ATSAchievement(BaseModel):
    achievement_type: str  # Certification, Award, Publication, Project, Competition, Patent, etc.
    achievement_title: str
    achievement_domain: Optional[str] = None
    organization_name: str
    timeline: str
    role_in_achievement: Optional[str] = None
    skills_demonstrated: Optional[List[str]] = None
    description: List[str]  # 2-3 detailed, keyword-rich paragraphs
    certificate_link: Optional[str] = None


# ============================================================
# ADVANCED ATS ACHIEVEMENT PROMPT
# ============================================================
prompt = PromptTemplate.from_template("""
You are an **elite ATS optimization expert and achievement storytelling specialist** with 15+ years of experience crafting compelling resume achievements for FAANG and Fortune 500 candidates.

Your mission: Transform raw achievement data into **powerful, ATS-optimized, multi-paragraph achievement descriptions** that maximize keyword density while maintaining natural readability and impressive impact.

CORE OBJECTIVE: Create achievement descriptions that:
- Score 95%+ on ATS keyword matching algorithms
- Pack maximum relevant technical keywords naturally across 2-3 paragraphs
- Emphasize **CREDENTIAL VALUE, TECHNICAL DEPTH, and PRACTICAL APPLICATION**
- Use **achievement-focused language** that demonstrates expertise and hands-on experience
- Are **comprehensive yet readable** - detailed paragraphs with rich technical context
- Appeal to both ATS algorithms AND human recruiters

---

## OUTPUT JSON SCHEMA

{{
  "achievement_type": "string (EXACT from raw data: Certification/Award/Publication/Project/Competition/Patent/etc.)",
  "achievement_title": "string (EXACT from raw data)",
  "achievement_domain": "string or null (EXACT from raw data)",
  "organization_name": "string (EXACT from raw data)",
  "timeline": "string (EXACT from raw data: 'Month Year' or 'Year')",
  "role_in_achievement": "string or null (EXACT from raw data)",
  "skills_demonstrated": ["skill1", "skill2", "skill3", ...],
  "description": [
    "First paragraph: Certificate/credential line if available, or primary achievement statement",
    "Second paragraph: Comprehensive technical details, hands-on experience, and technologies used",
    "Third paragraph (optional): Additional scope, outcomes, or learning outcomes covered"
  ],
  "certificate_link": "string or null (EXACT from raw data)"
}}

---

## ACHIEVEMENT DESCRIPTION FRAMEWORK

### Core Format (2-3 Paragraphs):

**Paragraph 1 (Certificate/Credential Line)**:
- If "certificate_link" exists: Use it as the credential statement
- Otherwise: Brief achievement statement with recognition/context
- Length: 5-12 words
- Example: "IBM Full Stack Software Developer Professional Certificate"

**Paragraph 2 (Technical Details & Experience)**:
- Main content paragraph with maximum ATS keywords
- Pattern: [Hands-on experience/Gained expertise] + [building/developing/implementing] + [project type] + using + [comprehensive tech stack list]
- Length: 25-40 words
- Must include ALL skills from "skills_demonstrated"

**Paragraph 3 (Scope & Coverage - Optional)**:
- Additional technical depth or learning outcomes
- Pattern: Covered + [development phases/concepts] + including + [additional technical areas]
- Length: 15-30 words
- Expand on methodologies, architecture, or domain knowledge

---

## ACHIEVEMENT TYPE-SPECIFIC TEMPLATES

### 1. CERTIFICATION

**Format**:
```
[Certificate/Credential Name from certificate_link or title]
Gained hands-on experience [building/developing/implementing] [application type] using [Tech1], [Tech2], [Tech3], and [TechN]. [Additional context about project/platform built].
Covered [phases/areas] including [concept1], [concept2], [concept3], and [conceptN].
```

**Example**:
```
IBM Full Stack Software Developer Professional Certificate
Gained hands-on experience building and deploying full-stack web applications using React.js, Next.js, Node.js, MongoDB, and REST API integration. Developed responsive frontend interfaces and robust backend services with authentication and database modeling.
Covered end-to-end development lifecycle including frontend design, component architecture, backend API logic, database schema design, testing, and cloud deployment strategies.
```

**Keyword Strategy**:
- Line 1: Official credential name (boosts credibility)
- Line 2: Action phrase + ALL technologies from skills_demonstrated
- Line 3: Development phases + architectural concepts + methodologies

---

### 2. AWARD/RECOGNITION

**Format**:
```
[Award Title] for [achievement context]
Recognized for [exceptional performance/innovation] in developing [solution type] using [comprehensive tech stack]. [Project impact or scope].
[Competition details] among [scale] demonstrating expertise in [technical areas].
```

**Example**:
```
First Place Award in National Hackathon
Recognized for developing innovative real-time collaboration platform using React, Redux, WebSockets, Node.js, Express, PostgreSQL, and Docker. Built scalable architecture supporting 1000+ concurrent users with sub-100ms latency.
Competed among 200+ teams nationwide demonstrating expertise in full-stack development, real-time communication protocols, database optimization, and cloud infrastructure deployment.
```

---

### 3. PROJECT (Personal/Academic/Research)

**Format**:
```
[Project Type]: [Project Name or Description]
Developed [application/system type] featuring [key features] using [comprehensive tech stack]. Implemented [technical achievements] with [specific technologies].
Demonstrated proficiency in [technical areas] including [concepts], achieving [outcomes if available].
```

**Example**:
```
Personal Project: E-Commerce Platform with Payment Integration
Developed full-stack e-commerce web application featuring user authentication, product catalog, shopping cart, and secure payment processing using React, TypeScript, Node.js, Express, MongoDB, Stripe API, and AWS deployment. Implemented responsive UI with Tailwind CSS and state management with Redux Toolkit.
Demonstrated proficiency in modern web development including RESTful API design, JWT authentication, database modeling, third-party API integration, and scalable cloud architecture deployment.
```

---

### 4. PUBLICATION/RESEARCH PAPER

**Format**:
```
Published [publication type] in [venue/platform]
[Research focus] exploring [technologies/methods] with [technical approach]. [Research contribution or findings].
Covered [technical areas] including [concepts] demonstrating expertise in [domain skills].
```

**Example**:
```
Published Research Paper in IEEE Conference Proceedings
Investigated distributed systems optimization exploring microservices architecture, Kubernetes orchestration, service mesh patterns, and load balancing algorithms using Go, Docker, and Istio. Proposed novel approach reducing inter-service latency by 35%.
Covered cloud-native technologies including containerization, service discovery, circuit breakers, observability patterns, and horizontal scaling strategies demonstrating expertise in distributed systems design.
```

---

### 5. COMPETITION/HACKATHON

**Format**:
```
[Placement] in [Competition Name]
Developed [solution description] using [comprehensive tech stack] within [timeframe]. [Key technical features or innovations].
Demonstrated [technical skills] including [concepts] while collaborating in [team context] and presenting to [judges/stakeholders].
```

**Example**:
```
Second Place in Google Cloud Hackathon 2024
Developed AI-powered code review assistant using Python, OpenAI GPT-4 API, LangChain, FastAPI, React, and Google Cloud Platform within 48-hour timeframe. Implemented automated code analysis, security vulnerability detection, and improvement suggestions with natural language explanations.
Demonstrated expertise in AI integration, prompt engineering, RESTful API development, cloud deployment, and real-time streaming while collaborating in 4-person team and presenting technical solution to industry expert judges.
```

---

### 6. PATENT/INTELLECTUAL PROPERTY

**Format**:
```
[Patent Status]: [Patent Title]
[Innovation description] using [technical implementation]. [Technical approach or methodology].
Addresses [problem domain] with applications in [industry/market] demonstrating expertise in [technical areas].
```

**Example**:
```
Patent Pending: ML-Based Query Optimization System
Novel database query optimization algorithm using machine learning models, adaptive indexing strategies, and real-time performance monitoring with Python, TensorFlow, and Redis caching. Reduces query execution time by predicting optimal index usage patterns.
Addresses database performance bottlenecks with applications in high-traffic web applications and big data analytics demonstrating expertise in database internals, machine learning, and systems optimization.
```

---

### 7. OPEN SOURCE CONTRIBUTION

**Format**:
```
[Contribution Role] to [Project Name]
Contributed [features/improvements] using [technologies] including [specific implementations]. [Impact on project].
Added [technical capabilities] demonstrating expertise in [technical areas] with [metrics if available].
```

**Example**:
```
Core Contributor to React UI Component Library
Contributed accessibility features, TypeScript migration, and comprehensive test suite using React, TypeScript, Jest, Testing Library, and Storybook. Improved component API design and added 50+ unit tests achieving 90% code coverage.
Added WCAG 2.1 AA compliance, keyboard navigation support, and screen reader compatibility demonstrating expertise in web accessibility, type safety, testing best practices, and component-driven development with 2K+ GitHub stars.
```

---

## MAXIMUM KEYWORD DENSITY STRATEGY

### MUST INCLUDE (Priority Order):
1. **ALL skills from "skills_demonstrated"** - Distribute across paragraphs
2. **Related technologies from "description" field** - Extract and expand
3. **Domain-specific terminology** from "achievement_domain"
4. **Development concepts**: Architecture, design patterns, methodologies
5. **Technical processes**: CI/CD, testing, deployment, optimization
6. **Tools/Platforms**: Git, Docker, AWS, cloud services
7. **Soft skills**: Collaboration, problem-solving, communication (when relevant)

### KEYWORD INTEGRATION TECHNIQUES:

**Technique 1: Comprehensive Listing**
- "using React, Redux, TypeScript, Node.js, Express, MongoDB, Docker, and AWS"
- "covering Python, TensorFlow, Keras, Pandas, NumPy, and scikit-learn"

**Technique 2: Hierarchical Grouping**
- "frontend technologies (React, TypeScript, Tailwind CSS), backend services (Node.js, Express, PostgreSQL), and cloud deployment (Docker, AWS, CI/CD)"

**Technique 3: Contextual Integration**
- "Implemented authentication using JWT tokens, OAuth 2.0, and bcrypt password hashing"
- "Built responsive UI with mobile-first design, CSS Grid, Flexbox, and accessibility standards"

**Technique 4: Process-Based Keywords**
- "end-to-end development including requirements gathering, system design, implementation, testing, and deployment"
- "full-stack architecture covering frontend components, REST APIs, database design, and infrastructure"

---

## PARAGRAPH-SPECIFIC KEYWORD DISTRIBUTION

### Paragraph 1 (Credential/Context):
- Focus: Official name, certification authority, credential type
- Keywords: Certification, professional, industry-recognized, specialized
- Keep concise: 5-12 words

### Paragraph 2 (Technical Core):
- Focus: Maximum technology keywords, hands-on experience, what was built
- Keywords: ALL skills_demonstrated + action verbs (built, developed, implemented, gained experience)
- Dense with technical terms: 25-40 words
- Must feel natural, not stuffed

### Paragraph 3 (Scope/Coverage):
- Focus: Development phases, architectural concepts, additional competencies
- Keywords: Methodologies, architecture patterns, best practices, soft skills
- Educational/comprehensive: 15-30 words

---

## SKILLS_DEMONSTRATED EXTRACTION RULES

**Build comprehensive skills list (8-15 items) by combining**:
1. ALL items explicitly in "skills_demonstrated" array
2. Technologies mentioned in "description" field
3. Related technologies (e.g., React → JavaScript, JSX, ES6)
4. Frameworks/libraries (e.g., Node.js → Express, npm)
5. Domain skills from "achievement_domain"
6. Development tools (Git, VS Code, Postman)
7. Methodologies (Agile, REST, MVC, microservices)

**Expansion Examples**:
- Input: ["React.js", "Node.js", "MongoDB"]
- Output: ["React.js", "JavaScript", "Node.js", "Express", "MongoDB", "REST API", "Full-Stack Development", "NoSQL", "Database Design", "Web Development"]

**Format**: Array of 8-15 skills, prioritized by ATS frequency and relevance

---

## ANTI-HALLUCINATION RULES

**ABSOLUTE PROHIBITIONS**:
1. ❌ NO METRIC INVENTION - Only use metrics/numbers from raw data
2. ❌ NO TECHNOLOGY ADDITION - Only use skills from "skills_demonstrated" and "description"
3. ❌ NO ORGANIZATION CHANGES - Keep "organization_name" EXACT
4. ❌ NO TITLE MODIFICATION - Keep "achievement_title" EXACT
5. ❌ NO DATE FABRICATION - Keep "timeline" EXACT
6. ❌ NO ROLE INVENTION - Keep "role_in_achievement" EXACT or null
7. ❌ NO CREDENTIAL INFLATION - Don't upgrade certification levels
8. ❌ NO FAKE OUTCOMES - Only mention results if in raw data

**VALIDATION CHECKLIST**:
- [ ] Every technology mentioned is from "skills_demonstrated" or "description"
- [ ] Timeline unchanged
- [ ] Organization name unchanged
- [ ] Achievement title unchanged
- [ ] Certificate link preserved exactly
- [ ] No invented metrics unless scale indicators
- [ ] 2-3 paragraphs (never 1, never more than 3)

---

## EDGE CASE HANDLING

### MINIMAL DATA (Only title, org, skills):
**Approach**: Focus on skills and infer typical learning/project scope
**Example**:
```
Professional certification in web development
Gained hands-on experience building web applications using HTML, CSS, JavaScript, React, and responsive design principles. Developed portfolio projects demonstrating frontend development skills.
Covered modern web development practices including component-based architecture, state management, and cross-browser compatibility.
```

### RICH DATA (Detailed description field):
**Approach**: Extract all technical terms, build comprehensive narrative
**Example**:
```
AWS Certified Solutions Architect Professional
Gained comprehensive expertise architecting and deploying scalable cloud infrastructure using AWS services including EC2, S3, Lambda, RDS, CloudFront, Route 53, VPC, and IAM. Designed multi-tier applications with high availability, fault tolerance, and disaster recovery.
Covered advanced AWS architecture patterns including microservices, serverless computing, Infrastructure as Code with Terraform and CloudFormation, cost optimization strategies, security best practices, and compliance frameworks.
```

### CERTIFICATE_LINK PROVIDED:
- Always use certificate_link content as Paragraph 1
- Example: "IBM Full Stack Software Developer Professional Certificate"

### NO CERTIFICATE_LINK:
- Create brief achievement statement as Paragraph 1
- Example: "Certification in Cloud Computing and DevOps"

---

## WRITING GUIDELINES

### Language Style:
- **Active Voice**: "Gained hands-on experience building..." NOT "Experience was gained..."
- **Past Tense**: For completed achievements
- **Technical but Accessible**: Detailed yet readable
- **Professional Tone**: Confident and achievement-focused

### Paragraph Rules:
- **No bullets**: Write in paragraph form
- **No periods at end**: ATS best practice for individual description items
- **Consistent Structure**: All paragraphs follow similar patterns
- **Natural Flow**: Should read smoothly, not like keyword soup

### Length Guidelines:
- **Paragraph 1**: 5-12 words (credential line or context)
- **Paragraph 2**: 25-40 words (core technical content)
- **Paragraph 3**: 15-30 words (scope/coverage)
- **Total**: 45-82 words across all paragraphs

---

## QUALITY ASSURANCE CRITERIA

**BEFORE OUTPUTTING, VERIFY**:
1. ✅ Exactly 2-3 paragraphs (never 1, never 4+)
2. ✅ ALL "skills_demonstrated" integrated naturally
3. ✅ First paragraph uses certificate_link if available
4. ✅ Second paragraph is keyword-rich technical core
5. ✅ Third paragraph expands scope/coverage (if needed)
6. ✅ No keyword stuffing - reads naturally
7. ✅ No invented data - everything traceable
8. ✅ Professional, confident, achievement-focused tone
9. ✅ No periods at end of paragraphs
10. ✅ Proper grammar throughout

---

## OUTPUT REQUIREMENTS

1. **PURE JSON OUTPUT** - No markdown, no code blocks, no explanations
2. **EXACT FIELD PRESERVATION** - Don't modify title, org, timeline, link
3. **DESCRIPTION AS ARRAY** - 2-3 string elements (paragraphs)
4. **COMPREHENSIVE SKILLS ARRAY** - 8-15 items extracted and expanded
5. **NATURAL LANGUAGE** - Must read well to humans
6. **MAXIMUM ATS KEYWORDS** - Distributed across paragraphs
7. **NO HALLUCINATION** - Only data from raw input

---

## PROCESSING STEPS

1. **Parse Raw Data**: Extract all fields, identify achievement type
2. **Extract Technologies**: Scan "skills_demonstrated" and "description" for ALL tech terms
3. **Select Template**: Choose pattern based on "achievement_type"
4. **Build Paragraph 1**: Use certificate_link or create context statement
5. **Build Paragraph 2**: Integrate ALL technologies with hands-on experience narrative
6. **Build Paragraph 3**: Add scope, coverage, or additional technical depth
7. **Expand Skills Array**: Build comprehensive list (8-15 skills)
8. **Validate**: Check against anti-hallucination rules
9. **Format Output**: Clean JSON with exact structure

---

**RAW ACHIEVEMENT DATA:**
{raw_achievement}

---

**YOUR TASK:**
1. Analyze raw achievement data - identify type, all technologies, context
2. Extract ALL technical skills from "skills_demonstrated" and "description"
3. Select appropriate template based on achievement_type
4. Build Paragraph 1: Certificate line or brief context (5-12 words)
5. Build Paragraph 2: Hands-on experience + ALL technologies (25-40 words)
6. Build Paragraph 3: Coverage/scope with additional depth (15-30 words)
7. Build skills_demonstrated array (8-15 items) with expansions
8. Ensure all data traceable to raw input (no invention)
9. Validate: natural language + maximum keywords + 2-3 paragraphs + no hallucination
10. Output ONLY valid JSON (no markdown, no explanations, no code blocks)

**CRITICAL REQUIREMENTS**:
- Description MUST be an array of 2-3 strings (paragraphs), NOT a single string
- Output ONLY the JSON object, nothing else
- Do NOT include any explanatory text, paragraphs breakdowns, or additional commentary
- Do NOT repeat the JSON multiple times
- The response should start with {{ and end with }}

**OUTPUT (VALID JSON ONLY):**
""")


# ============================================================
# JSON Extraction Utility - ENHANCED
# ============================================================
def extract_clean_json(text: str) -> dict:
    """
    Cleans LLM output and extracts the first valid JSON block.
    Handles markdown code blocks, extra whitespace, malformed JSON,
    and removes any text after the JSON object.
    """
    try:
        # Remove markdown code blocks
        text = re.sub(r"```(?:json)?", "", text)
        text = re.sub(r"```", "", text)
        text = text.strip()

        # Find the first complete JSON object
        # Look for opening brace
        start_idx = text.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found in response")
        
        # Find the matching closing brace
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx == -1:
            raise ValueError("No complete JSON object found in response")
        
        # Extract only the JSON object
        json_text = text[start_idx:end_idx]
        
        # Parse and return
        return json.loads(json_text)
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nExtracted text:\n{json_text if 'json_text' in locals() else text[:500]}")
    except Exception as e:
        raise ValueError(f"Error extracting JSON: {e}\nRaw text:\n{text[:500]}")


# ============================================================
# POST-PROCESSING: Anti-Hallucination Validation
# ============================================================
def validate_achievement_output(
    generated_json: Dict[str, Any],
    raw_achievement: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validates LLM output against raw input to prevent hallucinations.
    Ensures critical fields are preserved exactly and format is correct.
    """
    print("Running achievement validation...")

    # Preserve exact fields from raw data
    exact_fields = [
        "achievement_type",
        "achievement_title",
        "organization_name",
        "timeline",
        "certificate_link"
    ]
    
    for field in exact_fields:
        if field in raw_achievement:
            generated_json[field] = raw_achievement[field]

    # Preserve optional exact fields
    if "achievement_domain" in raw_achievement:
        generated_json["achievement_domain"] = raw_achievement["achievement_domain"]
    else:
        generated_json["achievement_domain"] = generated_json.get("achievement_domain")

    if "role_in_achievement" in raw_achievement:
        generated_json["role_in_achievement"] = raw_achievement["role_in_achievement"]
    else:
        generated_json["role_in_achievement"] = generated_json.get("role_in_achievement")

    # Validate description is array with 2-3 paragraphs
    description = generated_json.get("description", [])
    
    # If description is string, convert to array
    if isinstance(description, str):
        print("Warning: Description is string, converting to array")
        # Try to split by newlines or periods
        paragraphs = [p.strip() for p in description.split('\n') if p.strip()]
        if len(paragraphs) < 2:
            # Try splitting by double spaces or periods
            paragraphs = [p.strip() for p in re.split(r'[.]\s+', description) if p.strip()]
        generated_json["description"] = paragraphs[:3]  # Max 3 paragraphs
    
    description = generated_json.get("description", [])
    
    if not isinstance(description, list):
        print("Error: Description must be array")
        generated_json["description"] = ["Achievement description unavailable"]
    elif len(description) < 2:
        print(f"Warning: Only {len(description)} paragraph(s) - should be 2-3")
    elif len(description) > 3:
        print(f"Warning: {len(description)} paragraphs - trimming to 3")
        generated_json["description"] = description[:3]
    
    # Remove periods from end of paragraphs (ATS best practice)
    description = generated_json.get("description", [])
    generated_json["description"] = [p.rstrip('.') for p in description]

    # Validate skills_demonstrated against raw data
    raw_skills = raw_achievement.get("skills_demonstrated", [])
    raw_description = raw_achievement.get("description", "")
    
    if isinstance(raw_skills, list) and raw_skills:
        generated_skills = generated_json.get("skills_demonstrated", [])
        
        # Check if core raw skills are present in generated description
        description_text = " ".join(generated_json.get("description", [])).lower()
        missing_skills = [
            skill for skill in raw_skills
            if isinstance(skill, str) and skill.lower() not in description_text
        ]
        
        if missing_skills:
            print(f"Warning: Some skills not integrated into description: {missing_skills}")
        
        # Validate skills_demonstrated array - ensure all items are from raw data or logical expansions
        valid_skills = []
        all_raw_terms = raw_skills + raw_description.lower().split()
        
        for skill in generated_skills:
            if any(skill.lower() in str(term).lower() or str(term).lower() in skill.lower() 
                   for term in all_raw_terms):
                valid_skills.append(skill)
        
        # Ensure we have 8-15 skills (add back raw skills if validation removed too many)
        if len(valid_skills) < 5:
            valid_skills = list(set(valid_skills + raw_skills))[:15]
        
        generated_json["skills_demonstrated"] = valid_skills[:15]  # Cap at 15 skills
    
    # Validate paragraph lengths
    for i, para in enumerate(generated_json.get("description", [])):
        word_count = len(para.split())
        if i == 0 and word_count > 15:
            print(f"Warning: Paragraph 1 too long ({word_count} words, should be 5-12)")
        elif i == 1 and (word_count < 20 or word_count > 50):
            print(f"Warning: Paragraph 2 length suboptimal ({word_count} words, should be 25-40)")
        elif i == 2 and word_count > 35:
            print(f"Warning: Paragraph 3 too long ({word_count} words, should be 15-30)")
    
    # Ensure certificate_link is string or None
    if "certificate_link" in generated_json:
        if generated_json["certificate_link"] == "":
            generated_json["certificate_link"] = None

    print("Achievement validation complete")
    return generated_json


# ============================================================
# Main Function – Uses API key from header
# ============================================================
def format_ats_achievement_with_llm(achievement: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """
    Generates a clean, validated ATS-optimized achievement JSON.
    Uses the provided `api_key` from the `x-api-key` header.
    
    Args:
        achievement: Raw achievement data dictionary
        api_key: Groq API key from request header
        
    Returns:
        Validated ATS-optimized achievement dictionary with format:
        - description: Array of 2-3 paragraphs
        - skills_demonstrated: Array of 8-15 skills
    """
    print("Processing achievement with advanced ATS formatter...")
    print(f"Input data: {json.dumps(achievement, indent=2)}\n")

    # Create LLM instance with dynamic API key
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=api_key,
        temperature=0.1,
        max_tokens=2500
    )
    chain = prompt | llm

    # Invoke LLM
    ai_message = chain.invoke({"raw_achievement": json.dumps(achievement, indent=2)})
    llm_output = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
    print("\n[LLM RAW OUTPUT]\n", llm_output[:1500], "...\n")

    # Extract JSON
    clean_json = extract_clean_json(llm_output)
    print(f"Cleaned JSON: {json.dumps(clean_json, indent=2)}\n")

    # Validate against raw input
    validated_json = validate_achievement_output(clean_json, achievement)
    print(f"Validated JSON: {json.dumps(validated_json, indent=2)}\n")

    # Pydantic validation
    try:
        ats_data = ATSAchievement(**validated_json)
        final_json = ats_data.model_dump()
    except ValidationError as e:
        print(f"Pydantic validation error: {e}")
        print("Falling back to validated JSON without Pydantic enforcement")
        final_json = validated_json

    print("SUCCESS: ATS-optimized achievement JSON generated.")
    print(f"Final output: {json.dumps(final_json, indent=2)}")
    return final_json