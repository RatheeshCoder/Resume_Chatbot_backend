# src/services/education_resume.py
import json
import re
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, ValidationError
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from src.config import settings


# ============================================================
# Pydantic Schema for Education
# ============================================================
class ATSEducation(BaseModel):
    institution_name: str
    degree_or_course: str
    field_of_study: Optional[str] = None
    education_level: str  # Undergraduate, Graduate, Doctorate, Certificate, Diploma
    timeline: Dict[str, str]
    grade_or_cgpa: Optional[str] = None
    location: Optional[str] = None
    description: List[str]  # 2-5 achievement-focused bullet points
    relevant_coursework: Optional[List[str]] = None
    honors_and_awards: Optional[List[str]] = None
    skills_highlighted: Optional[List[str]] = None


# ============================================================
# ADVANCED ATS EDUCATION PROMPT
# ============================================================
prompt = PromptTemplate.from_template("""
You are an **elite FAANG resume writer, ATS optimization expert, and academic achievement specialist** with 15+ years of experience helping candidates showcase their education to land roles at Google, Amazon, Meta, Apple, Microsoft, and top-tier startups.

Your mission: Transform raw education data into **powerful, ATS-optimized, achievement-focused content** that maximizes keyword density, demonstrates academic excellence, and passes both ATS systems AND human recruiters.

CORE OBJECTIVE: Create education section content that:
- Scores 95%+ on ATS keyword matching for education-related searches
- Emphasizes **ACADEMIC ACHIEVEMENTS, PROJECTS, and RELEVANT SKILLS**
- Uses **strategic keyword placement** for maximum ATS visibility
- Highlights **hands-on experience, research, and technical competencies**
- Demonstrates **leadership, initiative, and extracurricular impact**
- Incorporates **relevant coursework and certifications** naturally

---

## OUTPUT JSON SCHEMA

{{
  "institution_name": "string (exact institution name from raw data)",
  "degree_or_course": "string (full degree name with proper formatting)",
  "field_of_study": "string or null (major/specialization)",
  "education_level": "string (Undergraduate/Graduate/Doctorate/Certificate/Diploma)",
  "timeline": {{
    "start_date": "Month Year",
    "end_date": "Month Year or Expected Month Year"
  }},
  "grade_or_cgpa": "string or null (GPA, CGPA, percentage, or honors)",
  "location": "string or null (city, state, country)",
  "description": [
    "Bullet 1: Primary academic achievement or major project with impact",
    "Bullet 2: Research, thesis, or significant coursework with technologies",
    "Bullet 3: Leadership role, club involvement, or extracurricular achievement",
    "Bullet 4 (optional): Additional project, competition, or recognition",
    "Bullet 5 (optional): Relevant training, certification, or skill development"
  ],
  "relevant_coursework": ["Course 1", "Course 2", "Course 3", ...],
  "honors_and_awards": ["Award 1", "Award 2", "Award 3", ...],
  "skills_highlighted": ["skill1", "skill2", "skill3", ...]
}}

---

## EDUCATION BULLET POINT FRAMEWORK

### Bullet 1: PRIMARY ACADEMIC ACHIEVEMENT OR CAPSTONE PROJECT
**Pattern**: [Action Verb] + [Project/Achievement] + [Technologies Used] + [Impact/Outcome]
**Focus**: Major project, thesis, research, or significant academic work
**Keywords**: Must include technical skills, tools, methodologies

**Examples**:
- "Developed AI-powered health monitoring system using Python, TensorFlow, IoT sensors, and Flask, achieving 94% accuracy in real-time vital signs prediction and presenting findings to faculty panel"
- "Led senior capstone project building full-stack e-commerce platform with React, Node.js, MongoDB, and AWS, deployed to production serving 500+ test users with 99.5% uptime"
- "Conducted machine learning research on predictive analytics using Python, scikit-learn, and pandas, analyzing 100K+ data points and publishing findings in college technical journal"
- "Engineered blockchain-based supply chain tracking system using Solidity, Ethereum, and Web3.js as final year project, winning Best Innovation Award among 50+ competing projects"

---

### Bullet 2: COURSEWORK, RESEARCH, OR TECHNICAL DEEP DIVE
**Pattern**: [Academic Action] + [Subject Area/Course] + [Technical Skills] + [Application/Result]
**Focus**: Relevant coursework, research methodology, technical training
**Keywords**: Course names, technologies, methodologies, frameworks

**Examples**:
- "Completed advanced coursework in Data Structures, Algorithms, Database Management Systems, and Cloud Computing, implementing 15+ complex projects using Java, Python, and SQL"
- "Conducted research on deep learning optimization techniques using PyTorch, CUDA, and TensorBoard, achieving 23% improvement in model training efficiency"
- "Gained hands-on experience in full-stack development through academic projects, mastering React, Express.js, PostgreSQL, Docker, and Git version control"
- "Studied software engineering principles including Agile methodologies, CI/CD pipelines, unit testing with Jest, and RESTful API design, applying concepts in 10+ team projects"

---

### Bullet 3: LEADERSHIP, EXTRACURRICULARS, OR COMMUNITY INVOLVEMENT
**Pattern**: [Leadership Action] + [Organization/Activity] + [Contribution/Impact] + [Skills Demonstrated]
**Focus**: Clubs, competitions, mentorship, teamwork, soft skills
**Keywords**: Leadership, collaboration, communication, teamwork, problem-solving

**Examples**:
- "Served as President of AI Club, organizing 12+ technical workshops on machine learning, data science, and Python programming for 80+ members, fostering collaborative learning environment"
- "Competed in 5+ national-level hackathons including Smart India Hackathon, securing top-10 finish and building solutions using MERN stack, Firebase, and cloud technologies"
- "Mentored 15 junior students in data structures and algorithms preparation, conducted weekly coding sessions, and improved their problem-solving skills for technical interviews"
- "Led team of 4 in inter-college coding competition, solving 8 algorithmic challenges in C++, Python, and Java within 3-hour time constraint, achieving 2nd place among 50 teams"

---

### Bullet 4: ADDITIONAL PROJECTS, COMPETITIONS, OR RECOGNITION (Optional)
**Pattern**: [Achievement Verb] + [Event/Project] + [Technical Details] + [Outcome]
**Focus**: Secondary projects, competitions, certifications, publications
**Keywords**: Competition names, project types, tools used, recognition

**Examples**:
- "Built real-time chat application using WebSocket, Node.js, React, and MongoDB as coursework project, implementing end-to-end encryption and supporting 100+ concurrent users"
- "Achieved top performer recognition in Artificial Intelligence and Data Science specialization, maintaining 8.6+ CGPA while completing 20+ technical projects"
- "Participated in Google Code Jam and Codeforces competitions, solving 150+ algorithmic problems and achieving 1800+ rating on competitive programming platforms"
- "Published research paper on IoT-based healthcare solutions in college symposium, presenting to audience of 200+ students and faculty members"

---

### Bullet 5: CERTIFICATIONS, TRAINING, OR SKILL DEVELOPMENT (Optional)
**Pattern**: [Learning Action] + [Certification/Training] + [Skills Acquired] + [Application]
**Focus**: Professional certifications, online courses, workshops, boot camps
**Keywords**: Certification names, platforms, skills learned, technologies

**Examples**:
- "Completed professional certifications in Python Programming, Machine Learning (Coursera), and Data Analytics (Google), strengthening foundation in data science and statistical analysis"
- "Earned AWS Certified Cloud Practitioner and Docker fundamentals certifications, demonstrating proficiency in cloud infrastructure and containerization technologies"
- "Participated in intensive 3-month web development boot camp, mastering HTML5, CSS3, JavaScript ES6+, React Hooks, and responsive design principles"
- "Attended workshops on Agile/Scrum methodologies, Git/GitHub collaboration, and software testing with Selenium, applying skills in academic team projects"

---

## CRITICAL ATS KEYWORD STRATEGY FOR EDUCATION

### MUST EMBED (High Priority):
1. **ALL technical skills from "key_learnings"** - Integrate naturally into bullets
2. **Relevant coursework keywords** - Specific course names, subject areas
3. **Technologies and tools** - Programming languages, frameworks, platforms
4. **Certifications** - Full certification names from "certificates_or_courses"
5. **Research areas** - Methodologies, domains, specializations
6. **Projects** - Project types, technologies used, outcomes
7. **Soft skills** - Leadership, teamwork, communication, problem-solving
8. **Academic terminology** - Capstone, thesis, research, coursework, GPA/CGPA

### POWER ACTION VERBS FOR EDUCATION:
**Project/Development**: Developed, Built, Engineered, Designed, Implemented, Created, Architected, Programmed
**Research/Analysis**: Conducted, Researched, Analyzed, Investigated, Studied, Examined, Explored, Published
**Leadership/Collaboration**: Led, Organized, Coordinated, Mentored, Facilitated, Managed, Collaborated, Contributed
**Achievement**: Achieved, Earned, Completed, Secured, Won, Received, Attained, Demonstrated
**Learning**: Gained, Mastered, Acquired, Strengthened, Enhanced, Specialized, Studied, Learned

### AVOID THESE WEAK PHRASES:
- Responsible for coursework, Attended classes, Took courses, Studied under, Was part of

---

## RELEVANT COURSEWORK OPTIMIZATION

**Extract and format from "certificates_or_courses" and general education data:**
- Use official course names when possible
- Group by category (e.g., "Core CS", "Data Science", "Web Development")
- Prioritize job-relevant courses
- Include 6-12 most relevant courses
- Use proper formatting with commas

**Example Output**:
```json
"relevant_coursework": [
  "Data Structures and Algorithms",
  "Database Management Systems",
  "Machine Learning",
  "Artificial Intelligence",
  "Cloud Computing",
  "Software Engineering",
  "Operating Systems",
  "Computer Networks",
  "Web Development",
  "Data Analytics"
]
```

---

## HONORS AND AWARDS FORMATTING

**Extract from "achievements_or_awards" and enhance with context:**
- Include official award names
- Add context if notable (e.g., "among 500+ students")
- List in reverse chronological order (most recent first)
- Include GPA/CGPA if 3.5+ (out of 4.0) or 8.0+ (out of 10.0)

**Examples**:
- "Best Project Award for AI-Powered Health Monitoring System"
- "Top Performer in Artificial Intelligence and Data Science Specialization"
- "Dean's List - All Semesters (8.6/10.0 CGPA)"
- "First Place in Inter-College Coding Competition (2023)"
- "Merit Scholarship Recipient for Academic Excellence"

---

## SKILLS EXTRACTION FOR EDUCATION

**Combine skills from multiple sources:**
1. All items from "key_learnings"
2. Technologies mentioned in "projects_or_research"
3. Skills from "certificates_or_courses"
4. Programming languages, frameworks, tools
5. Methodologies (Agile, Research Methods, etc.)
6. Soft skills (Leadership, Teamwork, Communication)

**Format**: ["Python", "Machine Learning", "TensorFlow", "Data Preprocessing", "IoT", "React", "Node.js", "Leadership", "Research", ...]

**Limit**: 15-20 most relevant skills

---

## EDUCATION LEVEL SPECIFIC GUIDELINES

### Undergraduate (Bachelor's):
- Emphasize **hands-on projects and technical skills**
- Highlight **relevant coursework and certifications**
- Include **club involvement and competitions**
- Show **growth and learning trajectory**
- Use 3-5 bullets focusing on projects, coursework, leadership

### Graduate (Master's):
- Emphasize **research and specialization**
- Highlight **thesis work or capstone projects**
- Include **publications and conferences**
- Show **advanced technical expertise**
- Use 3-5 bullets focusing on research, advanced projects, teaching/mentorship

### Doctorate (Ph.D.):
- Emphasize **original research and publications**
- Highlight **dissertation and findings**
- Include **grants, funding, presentations**
- Show **thought leadership and expertise**
- Use 4-5 bullets focusing on research contributions, publications, teaching

### Certificate/Diploma/Boot Camp:
- Emphasize **practical skills gained**
- Highlight **hands-on projects and portfolio work**
- Include **technologies mastered**
- Show **career-focused learning**
- Use 2-4 bullets focusing on skills, projects, certifications

---

## GPA/CGPA FORMATTING RULES

**Include GPA if:**
- GPA ≥ 3.5 (out of 4.0) OR
- CGPA ≥ 8.0 (out of 10.0) OR
- Percentage ≥ 80% OR
- Graduated with honors (Summa Cum Laude, Magna Cum Laude, Cum Laude, First Class, Distinction)

**Format examples:**
- "8.6/10.0 CGPA" or "8.6 CGPA"
- "3.8/4.0 GPA" or "3.8 GPA"
- "85%" or "85 Percent"
- "First Class with Distinction"
- "Summa Cum Laude"

**If below threshold**: Set `grade_or_cgpa` to `null`

---

## ANTI-HALLUCINATION RULES

**ABSOLUTE PROHIBITIONS**:
1. **NO INVENTION** - Use ONLY data from raw input
2. **NO FAKE PROJECTS** - Only mention projects from "projects_or_research"
3. **NO DEGREE INFLATION** - Keep degree name exactly as provided
4. **NO FALSE AWARDS** - Only use awards from "achievements_or_awards"
5. **NO FABRICATED COURSEWORK** - Only use courses from "certificates_or_courses" or reasonably infer from field_of_study
6. **NO FAKE SKILLS** - Only use skills from "key_learnings" or directly related to stated courses/projects

**VALIDATION CHECKLIST**:
- [ ] Every project mentioned is in "projects_or_research"
- [ ] Every award mentioned is in "achievements_or_awards" or reasonably inferred
- [ ] Every course is from "certificates_or_courses" or standard curriculum for the degree
- [ ] Skills are traceable to "key_learnings" or projects
- [ ] Degree and institution names match exactly
- [ ] Timeline matches exactly
- [ ] GPA/CGPA matches exactly (if provided)

---

## DEGREE AND FIELD FORMATTING

**Standardize degree names:**
- "Bachelor of Engineering in Computer Science" → "Bachelor of Engineering in Computer Science"
- "B.E. in Computer Science" → "Bachelor of Engineering in Computer Science"
- "M.Sc in Data Science" → "Master of Science in Data Science"
- "Ph.D. in Machine Learning" → "Doctor of Philosophy in Machine Learning"

**Field of study enhancement:**
- If specialization exists: "Artificial Intelligence and Data Science"
- If minor exists: "Computer Science (Minor in Mathematics)"
- Use exact text from raw data

---

## OUTPUT REQUIREMENTS

1. **NO MARKDOWN** - Output pure JSON only (no ```json``` blocks)
2. **2-5 Bullets** - Based on education level and available data
3. **Bullet Length** - 15-30 words per bullet (optimal for ATS parsing)
4. **First-Person Implied** - No "I", start with action verb
5. **Past Tense** - Unless currently enrolled (use present/expected completion)
6. **No Periods** - Bullets should not end with periods (ATS best practice)
7. **Consistent Format** - All bullets follow similar structure
8. **Keyword Density** - Maximize relevant keywords naturally

---

## PROCESSING STEPS

1. **Extract Core Info**: institution_name, degree_or_course, field_of_study, timeline, grade
2. **Identify All Skills**: Scan "key_learnings", "certificates_or_courses", "projects_or_research"
3. **Map Projects**: Convert "projects_or_research" to achievement bullets
4. **Extract Activities**: Pull from "activities_and_societies"
5. **Format Awards**: Process "achievements_or_awards" into honors_and_awards
6. **Build Coursework**: Extract from "certificates_or_courses" and enhance
7. **Create Bullets**: Combine projects, coursework, leadership, certifications
8. **Optimize Keywords**: Ensure all skills and technologies are naturally embedded
9. **Validate**: Check against anti-hallucination rules

---

**RAW EDUCATION DATA:**
{raw_education}

---

**YOUR TASK:**
1. Read raw data carefully - identify ALL projects, skills, achievements, coursework
2. Create 2-5 powerful bullet points emphasizing technical projects and achievements
3. Embed ALL skills from "key_learnings" naturally across bullets
4. Include relevant coursework from "certificates_or_courses"
5. Format honors and awards from "achievements_or_awards"
6. Extract 15-20 most relevant skills for "skills_highlighted"
7. Use power action verbs (Developed, Built, Led, Conducted, etc.)
8. Ensure maximum ATS keyword density without stuffing
9. Validate - no invented data, all traceable to raw input
10. Format GPA/CGPA properly (include if ≥3.5/4.0 or ≥8.0/10.0)
11. Output ONLY valid JSON (no markdown, no explanations)

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
def validate_education_output(
    generated_json: Dict[str, Any],
    raw_education: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validates LLM output against raw input to prevent hallucinations.
    Ensures all data is traceable to source.
    """
    print("Running education validation...")

    # Enforce exact matches for core fields
    for key in ("institution_name", "degree_or_course", "field_of_study", "education_level"):
        if key in generated_json and raw_education.get(key):
            generated_json[key] = raw_education[key]

    # Enforce exact timeline
    if "timeline" in raw_education:
        generated_json["timeline"] = raw_education["timeline"]

    # Enforce exact grade
    if "grade_or_cgpa" in raw_education:
        generated_json["grade_or_cgpa"] = raw_education["grade_or_cgpa"]
    else:
        generated_json["grade_or_cgpa"] = None

    # Enforce exact location
    if "location" in raw_education:
        generated_json["location"] = raw_education["location"]
    else:
        generated_json["location"] = None

    # Validate skills against key_learnings
    raw_learnings = raw_education.get("key_learnings", [])
    raw_certs = raw_education.get("certificates_or_courses", [])
    raw_projects = raw_education.get("projects_or_research", [])
    
    combined_skills = list(set(raw_learnings + raw_certs))
    
    if "skills_highlighted" in generated_json:
        # Ensure skills are traceable
        validated_skills = []
        for skill in generated_json["skills_highlighted"]:
            if any(skill.lower() in str(real).lower() for real in combined_skills):
                validated_skills.append(skill)
            elif any(skill.lower() in str(proj).lower() for proj in raw_projects):
                validated_skills.append(skill)
        
        generated_json["skills_highlighted"] = validated_skills[:20]

    # Validate relevant coursework
    if "relevant_coursework" in generated_json and raw_certs:
        validated_courses = [
            course for course in generated_json["relevant_coursework"]
            if any(course.lower() in str(cert).lower() for cert in raw_certs)
        ]
        generated_json["relevant_coursework"] = validated_courses[:12]
    elif not raw_certs:
        generated_json["relevant_coursework"] = None

    # Validate honors and awards
    if "honors_and_awards" in generated_json:
        raw_awards = raw_education.get("achievements_or_awards", [])
        if raw_awards:
            validated_awards = [
                award for award in generated_json["honors_and_awards"]
                if any(award.lower() in str(real_award).lower() for real_award in raw_awards)
            ]
            generated_json["honors_and_awards"] = validated_awards[:6]
        else:
            generated_json["honors_and_awards"] = None

    # Validate bullet count
    if "description" in generated_json:
        bullets = generated_json["description"]
        if len(bullets) < 2:
            print("Warning: Less than 2 bullets")
        elif len(bullets) > 6:
            print("Warning: More than 6 bullets - trimming")
            generated_json["description"] = bullets[:5]

    print("Education validation complete")
    return generated_json


# ============================================================
# Main Function – Uses API key from header
# ============================================================
def format_ats_education_with_llm(education: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """
    Generates a clean, validated ATS-optimized education JSON.
    Uses the provided `api_key` from the `x-api-key` header.
    """
    print("Processing education with advanced ATS formatter...")
    print(f"Input data: {json.dumps(education, indent=2)}\n")

    # Create LLM instance with dynamic API key
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=api_key,
        temperature=0.1,
        max_tokens=2500
    )
    chain = prompt | llm

    # Invoke LLM
    ai_message = chain.invoke({"raw_education": json.dumps(education, indent=2)})
    llm_output = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
    print("\n[LLM RAW OUTPUT]\n", llm_output[:1000], "...\n")

    # Extract JSON
    clean_json = extract_clean_json(llm_output)
    print(f"Cleaned JSON: {json.dumps(clean_json, indent=2)}\n")

    # Validate
    validated_json = validate_education_output(clean_json, education)
    print(f"Validated JSON: {json.dumps(validated_json, indent=2)}\n")

    # Pydantic validation
    try:
        ats_data = ATSEducation(**validated_json)
        final_json = ats_data.model_dump()
    except ValidationError as e:
        print(f"Pydantic validation error: {e}")
        final_json = validated_json

    print("SUCCESS: ATS-optimized education JSON generated.")
    print(f"Final output: {json.dumps(final_json, indent=2)}")
    return final_json