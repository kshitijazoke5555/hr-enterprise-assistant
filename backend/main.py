from fastapi import FastAPI, UploadFile, File, HTTPException, status, Request
import logging
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.rag_pipeline import run_rag

app = FastAPI(
    title="HR Enterprise Assistant",
    description="Department-aware RAG-based HR assistant",
    version="1.0"
)

# Allow frontend (vite) to call backend during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Models
# -----------------------------
class ChatRequest(BaseModel):
    username: str
    question: str
    department: str
    role: str
    country: str = None


class LoginRequest(BaseModel):
    username: str
    password: str


# -----------------------------
# Root
# -----------------------------
@app.get("/")
def root():
    return {"status": "HR Enterprise Assistant running"}


# -----------------------------
# Login
# -----------------------------
@app.post("/login")
async def login(req: Request):
    # Read raw JSON body to be tolerant of extra fields from frontend
    body = await req.json()
    # Log incoming login attempts for debugging frontend issues
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("uvicorn.access").info(f"[/login] request from {req.client.host}:{req.client.port} body={body}")

    # Demo credentials for testing
    demo_users = {
        "test_user": {"password": "password123", "role": "employee"},
        "emp": {"password": "emp123", "role": "employee"},
        "hr_bob": {"password": "hrpass", "role": "HR"}
    }

    # Extract username/password flexibly
    username = (body.get("username") or body.get("user") or "")
    password = body.get("password") or body.get("pass") or ""

    # Accept email in frontend by using the local-part for demo matching
    key = username.strip()
    if "@" in key:
        key_local = key.split("@")[0]
    else:
        key_local = key
    key_lower = key_local.lower()

    # find demo user case-insensitively
    user = None
    matched_username = None
    for uname, info in demo_users.items():
        if uname.lower() == key_lower:
            user = info
            matched_username = uname
            break

    # If caller provided a role and it's employee, allow any username with the demo employee password for testing
    provided_role = (body.get("role") or body.get("user_role") or "").lower()
    if provided_role == "employee":
        if password == demo_users["test_user"]["password"]:
            # accept the login; if username wasn't matched to demo user, use the provided username as-is
            return {"message": f"Welcome {key}", "username": key, "role": "employee"}
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials — check username/password")

    # fallback: require exact demo user match (e.g., HR demo)
    if not user or user.get("password") != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials — check username/password")

    return {"message": f"Welcome {matched_username}", "username": matched_username, "role": user.get("role")} 


# -----------------------------
# Upload Policy
# -----------------------------
@app.post("/upload")
def upload_policy(file: UploadFile = File(...)):
    return {
        "filename": file.filename,
        "status": "Uploaded successfully"
    }


# -----------------------------
# Chat Endpoint
# -----------------------------
@app.post("/chat")
def chat(request: ChatRequest):
    answer = run_rag(
        question=request.question,
        department=request.department,
        role=request.role,
        country=(request.country or None),
        username=request.username
    )
    # `answer` is a structured dict: return it directly
    return answer


# -----------------------------
# History (Placeholder)
# -----------------------------
@app.get("/history/{username}")
def get_history(username: str):
    return {
        "username": username,
        "history": []
    }
