# src/services/experience_resume.py
import json
import re
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, ValidationError
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from src.config import settings


# ============================================================
# Pydantic Schema for Experience
# ============================================================
class ATSExperience(BaseModel):
    title: str
    organization_name: str
    type: str  # Full-time, Part-time, Internship, Contract, Freelance
    timeline: Dict[str, str]
    location: Optional[str] = None
    description: List[str]  # 4-7 achievement-focused bullet points
    skills_highlighted: Optional[List[str]] = None


# ============================================================
# ADVANCED ATS EXPERIENCE PROMPT
# ============================================================
prompt = PromptTemplate.from_template("""
You are an **elite FAANG resume writer, ATS optimization expert, and career coach** with 15+ years of experience helping candidates land roles at Google, Amazon, Meta, Apple, Microsoft, and top-tier startups.

Your mission: Transform raw work experience data into **powerful, ATS-optimized, achievement-focused bullet points** that pass Applicant Tracking Systems AND impress human recruiters.

CORE OBJECTIVE: Create resume bullet points that:
- Score 95%+ on ATS keyword matching
- Follow the proven **X-Y-Z formula**: "Accomplished [X] as measured by [Y], by doing [Z]"
- Emphasize **IMPACT and RESULTS** over duties
- Use **power action verbs** that demonstrate leadership and technical expertise
- Incorporate **maximum relevant keywords** naturally without keyword stuffing
- Are **quantified** with metrics, percentages, timelines, or scale indicators

---

## OUTPUT JSON SCHEMA

{{
  "title": "string (exact job title from raw data)",
  "organization_name": "string (company name from raw data)",
  "type": "string (Full-time/Part-time/Internship/Contract/Freelance from raw data)",
  "timeline": {{
    "start_date": "Month Year",
    "end_date": "Month Year or Present"
  }},
  "location": "string or null (if available in raw data)",
  "description": [
    "Bullet 1: Primary achievement with quantified impact",
    "Bullet 2: Technical implementation or process improvement with tools",
    "Bullet 3: Cross-functional collaboration or leadership contribution",
    "Bullet 4: Additional technical achievement with specific technologies",
    "Bullet 5 (optional): Efficiency gain, cost savings, or quality improvement",
    "Bullet 6 (optional): Recognition, award, or business impact",
    "Bullet 7 (optional): Initiative or innovation driven"
  ],
  "skills_highlighted": ["skill1", "skill2", "skill3", ...]
}}

---

## BULLET POINT CREATION FRAMEWORK

### Formula: X-Y-Z (Google's Proven Method)
- **X** = What you accomplished (the action)
- **Y** = How it was measured (the metric)
- **Z** = How you did it (the method/tools)

**Example**: "Optimized database queries using indexing and query refactoring, reducing average response time by 45% and improving application throughput to handle 10K+ concurrent users"

---

## BULLET POINT STRUCTURE (Priority Order)

### Bullet 1: PRIMARY ACHIEVEMENT (Most Impactful Result)
**Pattern**: [Action Verb] + [What] + [Quantified Result] + [Method/Tools]
**Focus**: Business impact, major deliverable, or key responsibility
**Keywords**: Must include job-relevant technologies from "tools_and_technologies"

**Examples**:
- "Architected and deployed microservices-based payment system using Node.js, Docker, and AWS Lambda, processing $2M+ in monthly transactions with 99.9% uptime"
- "Led frontend development for enterprise SaaS platform using React, Redux, and TypeScript, increasing user engagement by 40% and reducing load time by 50%"
- "Engineered real-time data pipeline using Apache Kafka, Python, and PostgreSQL, processing 5M+ events daily with <100ms latency"

---

### Bullet 2: TECHNICAL IMPLEMENTATION (How You Built It)
**Pattern**: [Technical Action] + [Specific Technology/Method] + [Scale/Complexity] + [Result]
**Focus**: Technical depth, architecture, system design
**Keywords**: Frameworks, languages, methodologies, design patterns

**Examples**:
- "Implemented RESTful APIs and GraphQL endpoints using Express.js and Apollo Server, serving 500K+ daily requests across 15 microservices"
- "Designed responsive component library with React, Storybook, and Styled Components, adopted by 8 development teams and reducing UI development time by 30%"
- "Built automated CI/CD pipeline using Jenkins, Docker, and Kubernetes, decreasing deployment time from 2 hours to 15 minutes"

---

### Bullet 3: COLLABORATION/LEADERSHIP (Teamwork & Influence)
**Pattern**: [Collaborative Action] + [Cross-functional Team] + [Outcome] + [Technologies if applicable]
**Focus**: Teamwork, mentorship, stakeholder management, agile practices
**Keywords**: Agile, Scrum, cross-functional, stakeholders, code review, mentoring

**Examples**:
- "Collaborated with product managers, designers, and 6-person engineering team in Agile/Scrum environment to deliver 12+ features quarterly, maintaining 95% sprint completion rate"
- "Mentored 3 junior developers on React best practices, conducted weekly code reviews, and established coding standards that reduced bug count by 25%"
- "Partnered with UX/UI team to implement design system using Figma and Tailwind CSS, improving design-to-development handoff efficiency by 60%"

---

### Bullet 4: ADDITIONAL TECHNICAL CONTRIBUTION
**Pattern**: [Action] + [Technical Detail] + [Technology Stack] + [Benefit]
**Focus**: Secondary technical achievements, integrations, optimizations
**Keywords**: Integration, API, third-party services, debugging, testing

**Examples**:
- "Integrated OAuth 2.0 authentication with Auth0 and implemented JWT-based session management, enhancing security and supporting 50K+ active users"
- "Developed comprehensive test suite using Jest, React Testing Library, and Cypress, achieving 85% code coverage and reducing production bugs by 40%"
- "Optimized SQL queries and implemented Redis caching layer, reducing database load by 60% and improving API response times from 800ms to 150ms"

---

### Bullet 5: EFFICIENCY/OPTIMIZATION (Process Improvement)
**Pattern**: [Optimization Action] + [Method] + [Quantified Improvement] + [Business Impact]
**Focus**: Performance gains, cost savings, time reduction, quality improvements
**Keywords**: Optimized, automated, streamlined, reduced, improved, enhanced

**Examples**:
- "Automated manual reporting processes using Python scripts and AWS Lambda, saving 15 hours/week and eliminating human error in data aggregation"
- "Refactored legacy codebase from JavaScript to TypeScript, improving type safety, reducing runtime errors by 50%, and enhancing developer productivity"
- "Optimized image assets using WebP format and lazy loading with Intersection Observer API, reducing page load time by 40% and improving SEO rankings"

---

### Bullet 6: RECOGNITION/BUSINESS IMPACT (Optional)
**Pattern**: [Achievement Recognition] + [Context] + [Business Metric if available]
**Focus**: Awards, promotions, business outcomes, user satisfaction
**Keywords**: Achieved, recognized, awarded, contributed, resulted in

**Examples**:
- "Recognized as 'Developer of the Quarter' for exceptional performance and delivering critical features 2 weeks ahead of schedule"
- "Contributed to 35% increase in customer retention by developing personalized recommendation engine using machine learning and Python"
- "Drove $500K in annual cost savings by migrating infrastructure from on-premise servers to AWS using Terraform and Docker"

---

### Bullet 7: INNOVATION/INITIATIVE (Optional)
**Pattern**: [Proactive Action] + [Innovation] + [Adoption/Impact]
**Focus**: Self-driven projects, innovation, thought leadership
**Keywords**: Initiated, pioneered, introduced, championed, established

**Examples**:
- "Pioneered adoption of GraphQL federation across engineering organization, conducting workshops for 30+ developers and establishing best practices documentation"
- "Initiated weekly tech talks and knowledge-sharing sessions, fostering culture of continuous learning and improving team technical proficiency"
- "Championed accessibility improvements following WCAG 2.1 standards, achieving AA compliance and expanding user base by 20%"

---

## CRITICAL ATS KEYWORD STRATEGY

### MUST EMBED (High Priority):
1. **ALL tools from "tools_and_technologies"** - Integrate naturally into bullets
2. **Programming languages** - Python, JavaScript, TypeScript, Java, C++, Go, etc.
3. **Frameworks/Libraries** - React, Angular, Vue, Node.js, Django, Flask, Spring Boot, etc.
4. **Databases** - PostgreSQL, MongoDB, MySQL, Redis, Elasticsearch, DynamoDB, etc.
5. **Cloud/DevOps** - AWS, Azure, GCP, Docker, Kubernetes, Jenkins, CircleCI, Terraform, etc.
6. **Methodologies** - Agile, Scrum, CI/CD, TDD, microservices, RESTful APIs, GraphQL, etc.
7. **Domain-specific terms** from "domain_or_field"

### POWER ACTION VERBS (Use These):
**Technical Leadership**: Architected, Engineered, Designed, Built, Developed, Implemented, Created, Deployed, Launched
**Optimization**: Optimized, Enhanced, Improved, Streamlined, Automated, Refactored, Upgraded, Modernized
**Analysis**: Analyzed, Evaluated, Investigated, Researched, Diagnosed, Debugged, Troubleshot
**Collaboration**: Collaborated, Partnered, Coordinated, Led, Mentored, Facilitated, Guided, Trained
**Results**: Achieved, Delivered, Increased, Reduced, Accelerated, Exceeded, Generated, Drove

### AVOID THESE WEAK VERBS:
- Responsible for, Worked on, Helped with, Assisted, Involved in, Participated, Tasked with, Did

---

## QUANTIFICATION RULES

**ALWAYS TRY TO INCLUDE**:
- **Numbers**: Users (50K+), transactions ($2M+), requests (500K/day), records (1M+)
- **Percentages**: Improvements (40% faster), reductions (30% fewer bugs), increases (25% more traffic)
- **Timelines**: Development speed (2 weeks ahead), deployment frequency (10x faster)
- **Scale**: Team size (6-person team), scope (15 microservices), coverage (85%)

**If NO metrics in raw data**:
- Use scale indicators: "large-scale", "high-traffic", "enterprise-level"
- Use scope: "across 10+ services", "for 100+ enterprise clients"
- Use comparative: "significantly improved", "substantially reduced"

---

## ANTI-HALLUCINATION RULES

**ABSOLUTE PROHIBITIONS**:
1. NO INVENTION - Use ONLY data from raw input
2. NO FAKE METRICS - If no numbers provided, use qualitative impact instead
3. NO ROLE INFLATION - Keep title exactly as provided
4. NO TECHNOLOGY ADDITION - Only use tools from "tools_and_technologies"
5. NO OUTCOME FABRICATION - If "outcomes_or_achievements" is empty, infer from "what_you_did" but don't invent metrics

**VALIDATION CHECKLIST**:
- [ ] Every technology mentioned is in "tools_and_technologies" or "skills_gained"
- [ ] Metrics come from "outcomes_or_achievements" or are conservative scale indicators
- [ ] Role title matches "title" field exactly
- [ ] Timeline matches exactly
- [ ] No invented responsibilities beyond "role_and_responsibilities"

---

## SKILLS EXTRACTION

Extract "skills_highlighted" by combining:
1. All items from "tools_and_technologies"
2. All items from "skills_gained"
3. Key methodologies mentioned (e.g., Agile, CI/CD, REST API)
4. Domain-specific skills from "domain_or_field"

**Format**: ["React", "Node.js", "AWS", "Docker", "Agile", "Microservices", "REST APIs", ...]

---

## TYPE-SPECIFIC ADJUSTMENTS

### Internship:
- Emphasize **learning and contribution** balance
- Highlight **mentorship received** and **skills gained**
- Focus on **real-world application** of academic knowledge
- Example: "Gained hands-on experience in production React development, contributing to 5+ features under senior developer mentorship"

### Full-time:
- Emphasize **ownership and impact**
- Highlight **leadership and initiative**
- Focus on **business outcomes**

### Contract/Freelance:
- Emphasize **client satisfaction and delivery**
- Highlight **versatility and independence**
- Focus on **project completion and results**

---

## OUTPUT REQUIREMENTS

1. **NO MARKDOWN** - Output pure JSON only (no ```json``` blocks)
2. **4-7 Bullets** - More for senior roles, fewer for internships
3. **Bullet Length** - 15-25 words per bullet (optimal for ATS parsing)
4. **First-Person Implied** - No "I", just start with action verb
5. **Past Tense** - Unless current role (then use present tense)
6. **No Periods** - Bullets should not end with periods (ATS best practice)
7. **Consistent Format** - All bullets follow similar structure

---

## PROCESSING STEPS

1. **Extract Core Info**: title, organization, type, timeline
2. **Identify All Technologies**: Scan "tools_and_technologies" and "skills_gained"
3. **Map Responsibilities**: Convert "role_and_responsibilities" to achievement bullets
4. **Quantify**: Pull numbers from "outcomes_or_achievements"
5. **Integrate "what_you_did" and "how_you_did_it"**: Combine into cohesive bullets
6. **Apply X-Y-Z formula**: Ensure each bullet has accomplishment, measurement, method
7. **Optimize Keywords**: Ensure all technologies are naturally embedded
8. **Validate**: Check against anti-hallucination rules

---

**RAW EXPERIENCE DATA:**
{raw_experience}

---

**YOUR TASK:**
1. Read raw data carefully - identify ALL technologies, responsibilities, outcomes
2. Create 4-7 powerful bullet points using X-Y-Z formula
3. Embed ALL tools from "tools_and_technologies" naturally across bullets
4. Quantify everything possible from "outcomes_or_achievements"
5. Use power action verbs (Architected, Engineered, Optimized, etc.)
6. Ensure ATS keyword density is maximized without stuffing
7. Validate - no invented data, all traceable to raw input
8. Output ONLY valid JSON (no markdown, no explanations)

**OUTPUT (VALID JSON ONLY):**
""")


# ============================================================
# JSON Extraction Utility
# ============================================================
def extract_clean_json(text: str) -> dict:
    """
    Cleans LLM output and extracts the first valid JSON block.
    """
    try:
        text = re.sub(r"```(?:json)?", "", text)
        text = re.sub(r"```", "", text)
        text = text.strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw text:\n{text}")


# ============================================================
# POST-PROCESSING: Anti-Hallucination Validation
# ============================================================
def validate_experience_output(
    generated_json: Dict[str, Any],
    raw_experience: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validates LLM output against raw input to prevent hallucinations.
    Ensures all data is traceable to source.
    """
    print("Running experience validation...")

    for key in ("title", "organization_name", "type"):
        if key in generated_json and raw_experience.get(key):
            generated_json[key] = raw_experience[key]

    if "timeline" in raw_experience:
        generated_json["timeline"] = raw_experience["timeline"]

    raw_tools = raw_experience.get("tools_and_technologies", [])
    if isinstance(raw_tools, list) and raw_tools:
        description_text = " ".join(generated_json.get("description", [])).lower()
        missing_tools = [
            tool for tool in raw_tools
            if isinstance(tool, str) and tool.lower() not in description_text
        ]
        if missing_tools:
            print(f"Warning: Some tools not naturally integrated: {missing_tools}")

    if "skills_highlighted" in generated_json:
        raw_skills = raw_experience.get("skills_gained", [])
        combined_skills = list(set(raw_tools + raw_skills))
        generated_json["skills_highlighted"] = [
            skill for skill in generated_json["skills_highlighted"]
            if any(skill.lower() in str(real).lower() for real in combined_skills)
        ][:15]

    generated_json["location"] = generated_json.get("location") or None

    if "description" in generated_json:
        bullets = generated_json["description"]
        if len(bullets) < 3:
            print("Warning: Less than 3 bullets")
        elif len(bullets) > 8:
            print("Warning: More than 8 bullets - trimming")
            generated_json["description"] = bullets[:7]

    print("Experience validation complete")
    return generated_json


# ============================================================
# Main Function – Uses API key from header
# ============================================================
def format_ats_experience_with_llm(experience: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """
    Generates a clean, validated ATS-optimized experience JSON.
    Uses the provided `api_key` from the `x-api-key` header.
    """
    print("Processing experience with advanced ATS formatter...")
    print(f"Input data: {json.dumps(experience, indent=2)}\n")

    # Create LLM instance with dynamic API key
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=api_key,
        temperature=0.1,
        max_tokens=2500
    )
    chain = prompt | llm

    # Invoke LLM
    ai_message = chain.invoke({"raw_experience": json.dumps(experience, indent=2)})
    llm_output = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
    print("\n[LLM RAW OUTPUT]\n", llm_output[:1000], "...\n")

    # Extract JSON
    clean_json = extract_clean_json(llm_output)
    print(f"Cleaned JSON: {json.dumps(clean_json, indent=2)}\n")

    # Validate
    validated_json = validate_experience_output(clean_json, experience)
    print(f"Validated JSON: {json.dumps(validated_json, indent=2)}\n")

    # Pydantic validation
    try:
        ats_data = ATSExperience(**validated_json)
        final_json = ats_data.model_dump()
    except ValidationError as e:
        print(f"Pydantic validation error: {e}")
        final_json = validated_json

    print("SUCCESS: ATS-optimized experience JSON generated.")
    print(f"Final output: {json.dumps(final_json, indent=2)}")
    return final_json