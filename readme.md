# 1️⃣ Create a virtual environment
python -m venv venv

# 2️⃣ Activate the environment
# On Windows:
venv\Scripts\activate


# 3️⃣ Install all dependencies
pip install -r requirements.txt

# 4️⃣ Run the FastAPI server
uvicorn src.main:app --reload
