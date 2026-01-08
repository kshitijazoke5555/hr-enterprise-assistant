from datetime import datetime
from typing import List, Dict

# =============================
# METADATA FILTERING
# =============================

def filter_docs_by_access(
    docs: List[Dict],
    department: str,
    role: str
) -> List[Dict]:
    """
    Filter documents based on department & role access
    """
    filtered = []

    for doc in docs:
        meta = doc.metadata

        if meta.get("department") not in ["common", department]:
            continue

        allowed_roles = meta.get("allowed_roles", [])
        if allowed_roles and role not in allowed_roles:
            continue

        filtered.append(doc)

    return filtered


# =============================
# POLICY VERSION HANDLING
# =============================

def get_latest_policy(docs: List[Dict]):
    """
    Return latest policy version based on effective_date
    """
    return sorted(
        docs,
        key=lambda d: datetime.strptime(
            d.metadata.get("effective_date", "1970-01-01"),
            "%Y-%m-%d"
        ),
        reverse=True
    )[0]


def detect_policy_change(old_doc, new_doc) -> Dict:
    """
    Detect changes between policy versions
    """
    return {
        "previous_version": old_doc.metadata.get("version"),
        "current_version": new_doc.metadata.get("version"),
        "changed_on": new_doc.metadata.get("effective_date")
    }


# =============================
# CONFIDENCE SCORING
# =============================

def calculate_confidence(similarity_scores: List[float]) -> str:
    """
    Calculate confidence level from similarity scores
    """
    if not similarity_scores:
        return "LOW"

    avg_score = sum(similarity_scores) / len(similarity_scores)

    if avg_score >= 0.85:
        return "HIGH"
    elif avg_score >= 0.65:
        return "MEDIUM"
    return "LOW"


# =============================
# SAFE RESPONSE CHECKS
# =============================

def insufficient_coverage(docs: List[Dict]) -> bool:
    """
    Check if enough documents are retrieved
    """
    return len(docs) == 0
