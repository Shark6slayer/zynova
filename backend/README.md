# SUPER_AI Backend

FastAPI and MongoDB backend foundation for the SUPER_AI India-First Sovereign Super App.

## Stack
- Python 3.13 / FastAPI
- Async MongoDB driver (Motor & PyMongo)
- Pydantic v2
- Password hashing: Argon2id
- Token authentication: JWT (HS256) short-lived access tokens + refresh tokens

## Setup & Running Locally

### 1. Create and Activate Virtual Environment
```powershell
python -m venv c:\super_ai\backend\venv
.\backend\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r backend\requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item backend\.env.example backend\.env
```

### 4. Start MongoDB
Ensure MongoDB is running locally on port `27017` or update `MONGODB_URI` in `.env`.

### 5. Start Backend Server
```powershell
cd c:\super_ai\backend
.\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API Documentation:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### 6. Run Backend Tests
```powershell
cd c:\super_ai\backend
.\venv\Scripts\pytest tests
```
