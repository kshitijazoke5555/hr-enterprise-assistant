from typing import List, Optional, Tuple, Dict, Any
import re
import json
from langchain_chroma import Chroma
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings
)
from langchain_core.documents import Document
from backend.config import settings
from backend import db

def get_vectorstore():
    # Try several candidate vectorstore directories (ingest and db use different paths)
    candidates = [
        "backend/vectorstore",
        "./chroma_db",
        "chroma_db",
        "vectorstore",
    ]
    chosen = None
    import os
    for c in candidates:
        if os.path.exists(c):
            chosen = c
            break

    if not chosen:
        # fallback to the first candidate (will create when writing)
        chosen = candidates[0]

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=settings.GEMINI_API_KEY
    )

    return Chroma(
        persist_directory=chosen,
        embedding_function=embeddings
    )


def retrieve_documents(question: str, department: str, country: Optional[str] = None, k: int = 10, role: Optional[str] = None) -> Tuple[List[Document], bool]:
    """Retrieve documents relevant to the question and strictly filter by department and visibility.

    - Documents tagged with a `department` metadata that matches the requested department are prioritized.
    - Documents containing `common` in text or metadata are allowed.
    - Documents with visibility set to `HR_ONLY` are excluded for `employee` role.
    """
    vectorstore = get_vectorstore()

    docs = vectorstore.similarity_search(question, k=k)

    department_l = (department or "").lower()
    role_l = (role or "").lower()
    country_l = (country or "").lower()

    filtered_docs: List[Document] = []
    for doc in docs:
        text = (doc.page_content or "").lower()
        meta = {k.lower(): str(v).lower() for k, v in (doc.metadata or {}).items()}

        doc_dept = meta.get("department", "")
        doc_country = meta.get("country", "")
        visibility = meta.get("visibility", "all")
        source_name = meta.get("source", "") or meta.get("source_file", "")

        # Try to infer department from source filename if not explicitly provided
        if not doc_dept and source_name:
            sn = source_name.lower()
            if "hr" in sn or "hr_" in sn or "human" in sn:
                doc_dept = "hr"
            elif "it" in sn or "it_department" in sn or "it_" in sn:
                doc_dept = "it"
            elif "finance" in sn or "finance_" in sn or "payroll" in sn:
                doc_dept = "finance"
            elif "product" in sn or "product_" in sn:
                doc_dept = "product"
            elif "engineering" in sn or "engineer" in sn or "eng_" in sn:
                doc_dept = "engineering"
            elif "common" in sn or "company" in sn:
                doc_dept = "common"

        # Visibility: if document is HR-only and requester is an employee, skip
        if role_l == "employee" and visibility in ("hr", "hr_only", "hr-only"):
            continue

        # If a specific country/policy type was requested, require document country to match exactly
        if country_l:
            # require doc_country to be present and contain the requested country token
            if not doc_country:
                # skip documents without explicit country when user requested a specific country
                continue
            if country_l not in str(doc_country).lower():
                continue

        # Accept if department matches, or document marked common
        if (
            department_l and (department_l in text or department_l == doc_dept)
        ) or "common" in text or "common" in doc_dept:
            filtered_docs.append(doc)

    # If no strict matches found, attempt a relaxed fallback
    relaxed = False
    if not filtered_docs:
        # HR can see everything: return top matches
        if role_l == "hr":
            relaxed = True
            filtered_docs = docs
        else:
            # include any 'common' docs first
            common_docs = [d for d in docs if "common" in (d.page_content or "").lower() or "common" in str(d.metadata).lower()]
            if common_docs:
                relaxed = True
                filtered_docs = common_docs
            else:
                # as last resort, return top similarity matches but mark as relaxed
                relaxed = True
                filtered_docs = docs

    return filtered_docs, relaxed


def _fetch_conversation_history(username: str, limit: int = 6):
    session = db.SessionLocal()
    try:
        msgs = (
            session.query(db.ChatMessage)
            .filter(db.ChatMessage.session_id == username)
            .order_by(db.ChatMessage.timestamp.desc())
            .limit(limit)
            .all()
        )
        # return chronological order
        return list(reversed(msgs))
    finally:
        session.close()


def _save_chat_message(username: str, role: str, content: str, department: Optional[str] = None):
    session = db.SessionLocal()
    try:
        m = db.ChatMessage(session_id=username, role=role, content=content, department=(department or ""))
        session.add(m)
        session.commit()
    finally:
        session.close()


def generate_answer(question: str, documents: List[Document], department: str, role: str, username: Optional[str] = None, relaxed: bool = False) -> Dict[str, Any]:
    """Generate a structured response dict:
    {
      answer: str,
      suggested_follow_ups: [str],
      next_steps: str,
      confidence: int (optional, only for HR)
    }
    """
    if not documents:
        reply = (
            f"I searched {department}-specific and company-wide (common) policy documents and did not find any mention that answers your question. "
            "For confirmation, please consult your HR representative or submit a formal request for review."
        )
        if username:
            _save_chat_message(username, "assistant", reply, department=department)
        return {
            "answer": reply,
            "suggested_follow_ups": [
                "Do you mean paid time off for innovation projects or a formal leave type?",
                "Which team or product is this request for (so I can search more precisely)?"
            ],
            "next_steps": "I can broaden the search to related departments (IT/Product) or escalate this to HR. Which would you prefer?"
        }

    context = "\n\n".join(
        f"[{doc.metadata.get('policy_name', 'Policy')}]\n{doc.page_content}"
        for doc in documents
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0
    )

    system_prompt = f"""
You are an Enterprise HR Policy Assistant for a company.

Rules:
- Use ONLY the provided policy excerpts to answer; do not hallucinate or invent facts.
- Restrict answers to the {department} department when applicable; common policies are allowed.
- Follow a professional, respectful, and polite tone matching the user's formality.
- Provide a concise answer, then a one-sentence actionable next step if appropriate.
- At the end, suggest up to 2 relevant follow-up questions tailored to the user's conversation history.
Return the answer in clear natural language. Do not include internal notes.
"""

    preface = ""
    if relaxed and (role or "").lower() != "hr":
        preface = f"Note: The following retrieved policies may not be specific to the {department} department; they are the best matches available.\n\n"

    messages = [{"role": "system", "content": system_prompt}]
    if username:
        history_msgs = _fetch_conversation_history(username)
        for h in history_msgs:
            role_label = "user" if (h.role or "").lower() == "user" else "assistant"
            messages.append({"role": role_label, "content": h.content})

    user_prompt = f"""
{preface}Policies:
{context}

Previous question: {question}

Answer clearly and politely. Also provide 0-2 suggested follow-up questions based on previous context.
"""

    messages.append({"role": "user", "content": user_prompt})

    llm_response = llm.invoke(messages).content

    # Save user + assistant messages
    if username:
        _save_chat_message(username, "user", question, department=department)
        _save_chat_message(username, "assistant", llm_response, department=department)

    final_answer = llm_response.strip()

    # Sanitize final_answer: strip trailing suggestion/next-step sections
    def _strip_sections(text: str) -> str:
        lower = text.lower()
        markers = [
            "next step:", "next steps:",
            "suggested follow-up", "suggested follow-ups",
            "suggested follow-up questions", "suggested follow-ups:",
            "suggested follow ups", "suggested questions",
            "suggestions:", "follow-up questions:"
        ]
        idxs = []
        for m in markers:
            i = lower.find(m)
            if i != -1:
                idxs.append(i)
        if not idxs:
            return text.strip()
        cut = min(idxs)
        return text[:cut].strip()

    final_answer = _strip_sections(final_answer)

    # Compute confidence only for HR role
    confidence_score: Optional[int] = None
    if (role or "").lower() in ("hr", "human resources"):
        eval_prompt = (
            "Please provide a single numeric confidence score (0-100) that indicates how much of the answer above is directly supported by the provided policy excerpts. "
            "Respond with only the number and no additional text.\n\n"
            f"Policies:\n{context}\n\nAnswer:\n{final_answer}"
        )
        try:
            eval_resp = llm.invoke([
                {"role": "system", "content": "You are an objective evaluator that returns a single number."},
                {"role": "user", "content": eval_prompt}
            ]).content
            m = re.search(r"(\d{1,3})", eval_resp)
            if m:
                confidence_score = max(0, min(100, int(m.group(1))))
            else:
                confidence_score = 80
        except Exception:
            confidence_score = 80

    # Request structured JSON for suggestions and next steps from the LLM
    suggested: List[str] = []
    next_steps: str = ""
    try:
        struct_prompt = (
            "Given the provided policies and the assistant answer, return a JSON object with the keys:\n"
            "- answer: a concise, user-facing answer string\n"
            "- suggested_follow_ups: an array of up to 2 short follow-up question strings\n"
            "- next_steps: one short actionable next step the user can take\n"
            "Return ONLY valid JSON. Do not include any commentary.\n\n"
            f"Policies:\n{context}\n\nAnswer:\n{final_answer}"
        )
        struct_resp = llm.invoke([
            {"role": "system", "content": "You are a helpful assistant that outputs strict JSON."},
            {"role": "user", "content": struct_prompt}
        ]).content
        parsed = json.loads(struct_resp)
        answer_text = parsed.get("answer", final_answer)
        suggested = parsed.get("suggested_follow_ups", []) or []
        next_steps = parsed.get("next_steps", "") or ""
    except Exception:
        # Fallback heuristics
        answer_text = final_answer
        lines = [l.strip("-* ") for l in final_answer.splitlines() if l.strip()]
        for l in lines:
            if len(suggested) >= 2:
                break
            if l.lower().startswith("suggest") or l.endswith("?"):
                suggested.append(l)
        if not suggested:
            suggested = [
                "Do you mean paid time off for innovation projects or a formal leave type?",
                "Which team or product is this request for (so I can search more precisely)?"
            ]
        next_steps = "I can broaden the search to related departments (IT/Product) or escalate this to HR. Which would you prefer?"

    result: Dict[str, Any] = {
        "answer": answer_text,
        "suggested_follow_ups": suggested,
        "next_steps": next_steps
    }

    if confidence_score is not None:
        result["confidence"] = confidence_score

    return result


def run_rag(question: str, department: str, role: str, username: Optional[str] = None, country: Optional[str] = None) -> Dict[str, Any]:
    documents, relaxed = retrieve_documents(question, department, country=country, role=role)
    return generate_answer(question, documents, department, role, username=username, relaxed=relaxed)
