from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import requests
import os
import secrets
import msal
from backend.config import settings
from backend.rag_pipeline import run_rag
from backend import db

app = FastAPI(title="HR Enterprise Assistant API")

# Allow local frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores (for demo). Replace with persistent store in production.
_state_store: Dict[str, str] = {}
_session_store: Dict[str, Dict[str, Any]] = {}

# Azure AD config from env
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_REDIRECT_URI = os.getenv("AZURE_REDIRECT_URI", "http://localhost:8000/auth/callback")
AZURE_SCOPES = ["openid", "profile", "User.Read"]


def _build_msal_app():
    if not (AZURE_CLIENT_ID and AZURE_CLIENT_SECRET and AZURE_TENANT_ID):
        raise RuntimeError("Azure AD configuration missing. Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID in env.")
    authority = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
    return msal.ConfidentialClientApplication(
        AZURE_CLIENT_ID,
        authority=authority,
        client_credential=AZURE_CLIENT_SECRET
    )


@app.get("/login")
def login():
    """Redirect user to Azure AD login page."""
    app_msal = _build_msal_app()
    state = secrets.token_urlsafe(16)
    auth_url = app_msal.get_authorization_request_url(
        scopes=AZURE_SCOPES,
        redirect_uri=AZURE_REDIRECT_URI,
        state=state
    )
    _state_store[state] = "init"
    return RedirectResponse(url=auth_url)


# Demo POST login to support local frontend testing (mirrors backend.main demo)
@app.post("/login")
async def demo_login(request: Request):
    body = await request.json()
    demo_users = {
        "test_user": {"password": "password123", "role": "employee"},
        "emp": {"password": "emp123", "role": "employee"},
        "hr_bob": {"password": "hrpass", "role": "HR"}
    }

    username = (body.get("username") or body.get("user") or "").strip()
    password = body.get("password") or body.get("pass") or ""
    provided_role = (body.get("role") or body.get("user_role") or "").lower()

    # Accept either plain username or an email address; use local-part for demo matching
    username_local = username
    if "@" in username_local:
        username_local = username_local.split("@")[0]

    # employee shortcut
    if provided_role == "employee":
        if password == demo_users["test_user"]["password"]:
            session_id = secrets.token_urlsafe(24)
            user_info = {"name": username, "email": username, "department": (body.get("department") or "").lower(), "country": (body.get("country") or "").lower(), "roles": ["employee"]}
            _session_store[session_id] = user_info
            resp = JSONResponse({"message": f"Welcome {username}", "username": username, "role": "employee"})
            resp.set_cookie("session", session_id, httponly=True)
            return resp
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials — check username/password")

    # exact match
    user = None
    matched_username = None
    for uname, info in demo_users.items():
        if uname.lower() == username_local.lower():
            user = info
            matched_username = uname
            break

    if not user or user.get("password") != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials — check username/password")

    session_id = secrets.token_urlsafe(24)
    # Keep provided email if present, but use matched username for name/id
    user_info = {"name": matched_username, "email": username, "department": (body.get("department") or "").lower(), "country": (body.get("country") or "").lower(), "roles": [user.get("role")]}
    _session_store[session_id] = user_info
    resp = JSONResponse({"message": f"Welcome {matched_username}", "username": matched_username, "role": user.get("role")})
    resp.set_cookie("session", session_id, httponly=True)
    return resp


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle Azure AD redirect and create a server-side session."""
    params = dict(request.query_params)
    code = params.get("code")
    state = params.get("state")
    if not code or not state or state not in _state_store:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid auth callback parameters")

    app_msal = _build_msal_app()
    result = app_msal.acquire_token_by_authorization_code(
        code,
        scopes=AZURE_SCOPES,
        redirect_uri=AZURE_REDIRECT_URI
    )

    if "error" in result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result.get("error_description") or result.get("error"))

    id_claims = result.get("id_token_claims", {})
    # Try to extract department and country from claims, fall back to defaults
    user_info = {
        "name": id_claims.get("name") or id_claims.get("preferred_username") or "",
        "email": id_claims.get("preferred_username") or id_claims.get("upn") or "",
        "department": (id_claims.get("department") or "").lower(),
        "country": (id_claims.get("country") or id_claims.get("countryCode") or "").lower(),
        "roles": id_claims.get("roles", [])
    }

    # If department/country are missing from ID token, call Microsoft Graph to fetch the user's profile
    access_token = result.get("access_token")
    if access_token and (not user_info.get("department") or not user_info.get("country")):
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            graph_resp = requests.get("https://graph.microsoft.com/v1.0/me?$select=displayName,mail,department,country", headers=headers, timeout=5)
            if graph_resp.status_code == 200:
                profile = graph_resp.json()
                if not user_info.get("department") and profile.get("department"):
                    user_info["department"] = str(profile.get("department") or "").lower()
                if not user_info.get("country") and profile.get("country"):
                    user_info["country"] = str(profile.get("country") or "").lower()
                # prefer mail if email empty
                if not user_info.get("email") and profile.get("mail"):
                    user_info["email"] = profile.get("mail")
                if not user_info.get("name") and profile.get("displayName"):
                    user_info["name"] = profile.get("displayName")
        except Exception:
            pass

    # Create session
    session_id = secrets.token_urlsafe(24)
    _session_store[session_id] = user_info

    response = RedirectResponse(url="/")
    # Set cookie (httponly). In production, set secure=True and SameSite settings appropriately.
    response.set_cookie("session", session_id, httponly=True)
    return response


@app.post("/query")
async def query(request: Request):
    """Accepts JSON {"question": "..."} and returns filtered answers based on user's department and country."""
    session_id = request.cookies.get("session")
    if not session_id or session_id not in _session_store:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = _session_store[session_id]
    body = await request.json()
    question = body.get("question")
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question required")

    user_dept = (user.get("department") or "").lower()
    user_country = (user.get("country") or "").lower()
    roles_list = [(r or "").lower() for r in (user.get("roles") or [])]
    user_role = "hr" if any(r in ("hr", "human resources") for r in roles_list) else "employee"

    # Optional: policy_country allows the frontend to request 'india' or 'foreign' policies specifically
    body = body or {}
    policy_country = (body.get("policy_country") or body.get("policy_type") or body.get("country") or "").lower() or None
    # normalize common aliases
    if policy_country in ("india", "indian", "indian_policy"):
        policy_country = "india"
    if policy_country in ("foreign", "international", "foreign_policy"):
        policy_country = "foreign"

    try:
        reply = run_rag(question, department=user_dept or "", role=user_role, username=user.get("email"), country=policy_country or user_country or None)
    except Exception as e:
        # Fallback: return empty result with error
        return JSONResponse({"answer": "", "documents": [], "error": str(e)})

    return JSONResponse(reply)


@app.get('/history')
async def get_history(department: str):
    """Return a list of recent user questions (threads) for the given department.

    Each item corresponds to a single user question (role='user') so the frontend
    shows questions as the history list. The frontend can then request the
    matching Q/A pair using the message id.
    """
    session = db.SessionLocal()
    try:
        rows = (
            session.query(db.ChatMessage)
            .filter(db.ChatMessage.department == (department or "").lower(), db.ChatMessage.role == 'user')
            .order_by(db.ChatMessage.timestamp.desc())
            .all()
        )
        out = [{"message_id": m.id, "session_id": m.session_id, "question": (m.content or "")[:400], "timestamp": m.timestamp.isoformat()} for m in rows]
        return JSONResponse(out)
    finally:
        session.close()


@app.get('/history/thread/{user_message_id}')
async def get_history_thread(user_message_id: int, department: str):
    """Return the user question and the immediate assistant reply for the given user message id and department.

    This keeps history items concise (one entry per question) while allowing
    the frontend to show the full Q/A when clicked.
    """
    session = db.SessionLocal()
    try:
        user_msg = session.query(db.ChatMessage).filter(db.ChatMessage.id == user_message_id, db.ChatMessage.role == 'user', db.ChatMessage.department == (department or "").lower()).first()
        if not user_msg:
            return JSONResponse([], status_code=404)

        # find the first assistant reply after the user message with same session_id
        assistant_msg = session.query(db.ChatMessage).filter(
            db.ChatMessage.session_id == user_msg.session_id,
            db.ChatMessage.role == 'assistant',
            db.ChatMessage.department == (department or "").lower(),
            db.ChatMessage.timestamp >= user_msg.timestamp
        ).order_by(db.ChatMessage.timestamp.asc()).first()

        out = []
        out.append({"role": "user", "content": user_msg.content, "timestamp": user_msg.timestamp.isoformat()})
        if assistant_msg:
            out.append({"role": "assistant", "content": assistant_msg.content, "timestamp": assistant_msg.timestamp.isoformat()})
        return JSONResponse(out)
    finally:
        session.close()
