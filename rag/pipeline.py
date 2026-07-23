"""
DPU EduBot — RAG Pipeline
Zero-hallucination 4-layer architecture:
  Layer 0: Personal ERP data → redirect immediately, no LLM call
  Layer 1: FAQ knowledge base → answer from verified FAQs
  Layer 2: Batch-specific data → answer from batch documents
  Layer 3: Website data → general program info
"""

import os
import sys
import json
import pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "mock_key")

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
CONF_THRESHOLD = 0.50
import tempfile
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(tempfile.gettempdir(), "faiss_index", "index.npy")
CHUNKS_PATH = os.path.join(tempfile.gettempdir(), "faiss_index", "chunks.pkl")
KB_PATH = os.path.join(ROOT_DIR, "data", "knowledge_base.json")

# ════════════════════════════════════════════════════════════════════
# MOCK DATA — 5 sample students (extracted from erp_demo.py)
# ════════════════════════════════════════════════════════════════════
MOCK_STUDENTS = {
    "ERP001": {
        "name": "Pratap Nayadkar", "program": "MBA Online", "batch": "MBA Jan 2026",
        "semester": 1, "specialization": "Marketing", "prn": "DPU2026MBA001",
        "mentor": "Ms. Sneha Mehta",
        "fees": {"total": 189400, "paid": 50000, "outstanding": 139400,
                 "sem1": "Paid (Rs 50,000 on 5 Jan 2026)",
                 "sem2": "Due Rs 50,000 by 15 Feb 2026"},
        "assignments": {"total": 14, "submitted": 9, "pending": 5,
                        "pending_list": [
                            "OMBC-103 Management Accounting — Assignment 2",
                            "OMBC-105 Business Communication — Assignment 1 & 2",
                            "OMBC-107 Environmental Awareness — Assignment 1 & 2"]},
        "exam": {"form": "Submitted", "admit_card": "Available on ERP",
                 "exam_date": "5 March 2026 (Tentative)", "result": "Not declared",
                 "backlog": []},
        "attendance": 78,
        "books": "Delivered on 12 January 2026"
    },
    "ERP002": {
        "name": "Riya Sharma", "program": "MBA Online", "batch": "MBA Jan 2026",
        "semester": 1, "specialization": "Finance", "prn": "DPU2026MBA002",
        "mentor": "Mr. Vivek Nair",
        "fees": {"total": 189400, "paid": 100000, "outstanding": 89400,
                 "sem1": "Paid", "sem2": "Paid (Rs 50,000 on 5 Feb 2026)"},
        "assignments": {"total": 14, "submitted": 14, "pending": 0, "pending_list": []},
        "exam": {"form": "Submitted", "admit_card": "Available on ERP",
                 "exam_date": "5 March 2026", "result": "Not declared", "backlog": []},
        "attendance": 92,
        "books": "Delivered on 10 January 2026"
    },
    "ERP003": {
        "name": "Arjun Mehta", "program": "MBA Online", "batch": "MBA Jan 2026",
        "semester": 1, "specialization": "Operations Management", "prn": "DPU2026MBA003",
        "mentor": "Ms. Priya Rao",
        "fees": {"total": 189400, "paid": 0, "outstanding": 189400,
                 "sem1": "OVERDUE — Rs 50,000 pending since 15 Jan 2026",
                 "sem2": "Not yet due"},
        "assignments": {"total": 14, "submitted": 0, "pending": 14,
                        "pending_list": ["All assignments locked — fees pending"]},
        "exam": {"form": "Not submitted (fees pending)",
                 "admit_card": "Not eligible — pay fees first",
                 "exam_date": "5 March 2026", "result": "Not eligible", "backlog": []},
        "attendance": 0,
        "books": "Not dispatched — awaiting fee payment"
    },
    "ERP006": {
        "name": "Sneha Iyer", "program": "BBA Online", "batch": "BBA Jan 2026",
        "semester": 1, "specialization": "Marketing", "prn": "DPU2026BBA042",
        "mentor": "Ms. Priya Rao",
        "fees": {"total": 165000, "paid": 55000, "outstanding": 110000,
                 "sem1": "Paid (Rs 55,000 on 7 Jan 2026)",
                 "sem2": "Due Rs 55,000 by 1 March 2026"},
        "assignments": {"total": 10, "submitted": 7, "pending": 3,
                        "pending_list": [
                            "OBBAC-103 Introduction to Economics — Assignment 2",
                            "OBBAC-105 Business English — Assignment 1 & 2"]},
        "exam": {"form": "Submitted", "admit_card": "Available on ERP",
                 "exam_date": "20 May 2026", "result": "Not declared", "backlog": []},
        "attendance": 81,
        "books": "Delivered on 14 January 2026"
    },
    "ERP009": {
        "name": "Vikram Joshi", "program": "MBA Online", "batch": "MBA Jul 2024",
        "semester": 4, "specialization": "Business Analytics", "prn": "DPU2024MBA152",
        "mentor": "Mr. Arjun Kumar",
        "fees": {"total": 189400, "paid": 189400, "outstanding": 2500,
                 "sem1": "Paid", "sem2": "Paid"},
        "assignments": {"total": 14, "submitted": 14, "pending": 0, "pending_list": []},
        "exam": {"form": "Submitted (with 1 backlog)", "admit_card": "Available on ERP",
                 "exam_date": "10 March 2026",
                 "result": "Sem 1: 7.2 | Sem 2: 7.5 | Sem 3: FAIL in OMBC-303",
                 "backlog": ["OMBC-303 Strategic Management"]},
        "attendance": 86,
        "books": "Delivered on 18 January 2026"
    },
}

# Load knowledge base for Layer 0 rules
with open(KB_PATH, encoding="utf-8") as f:
    KB = json.load(f)

LAYER0_TRIGGERS = KB["layer_0_redirect_rules"]["triggers"]
LAYER0_REDIRECTS = KB["layer_0_redirect_rules"]["redirects"]


# ─── Layer 0: Personal data redirect ──────────────────────────────

def check_layer0(query: str) -> dict | None:
    """
    Check if query is asking for personal ERP data.
    If yes, return the redirect info immediately.
    If no, return None and proceed to RAG.
    """
    q = query.lower().strip()
    for trigger in LAYER0_TRIGGERS:
        if trigger in q:
            # Map trigger to redirect bucket
            if "attendance" in trigger:
                return LAYER0_REDIRECTS["attendance"]
            if any(x in trigger for x in ["fee", "payment", "receipt"]):
                return LAYER0_REDIRECTS["fees"]
            if any(x in trigger for x in ["result", "marks", "grade", "cgpa"]):
                return LAYER0_REDIRECTS["result"]
            if any(x in trigger for x in ["admit card", "hall ticket"]):
                return LAYER0_REDIRECTS["admit_card"]
            if any(x in trigger for x in ["assignment status", "did i submit", "my submission"]):
                return LAYER0_REDIRECTS["assignment_status"]
            if "mentor" in trigger:
                return LAYER0_REDIRECTS["mentor"]
            if any(x in trigger for x in ["profile", "erp id", "prn", "student id"]):
                return LAYER0_REDIRECTS["profile"]
            if "backlog" in trigger:
                return LAYER0_REDIRECTS["result"]
    return None


USE_MOCK = False

def embed_text(text: str) -> np.ndarray:
    """Get embedding vector, with fallback to deterministic mock vector on error."""
    global USE_MOCK
    if not USE_MOCK:
        try:
            res = client.embeddings.create(input=[text], model=EMBED_MODEL, timeout=5.0)
            return np.array(res.data[0].embedding, dtype="float32")
        except Exception as e:
            print(f"[Warning] API call failed: {e}. Switching to offline fallback embeddings.")
            USE_MOCK = True

    import hashlib
    h = hashlib.sha256(text.encode('utf-8')).digest()
    seed = int.from_bytes(h[:4], 'big')
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(1536).astype("float32")
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec



# ─── Index loading ────────────────────────────────────────────────

_index_cache = None
_chunks_cache = None


def load_index():
    """Load numpy index and chunks from disk (cached)."""
    global _index_cache, _chunks_cache
    if _index_cache is not None:
        return _index_cache, _chunks_cache

    try:
        if os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH):
            _index_cache = np.load(INDEX_PATH)
            with open(CHUNKS_PATH, "rb") as f:
                _chunks_cache = pickle.load(f)
        else:
            fallback_index = os.path.join(ROOT_DIR, "data", "faiss_index", "index.npy")
            fallback_chunks = os.path.join(ROOT_DIR, "data", "faiss_index", "chunks.pkl")
            _index_cache = np.load(fallback_index)
            with open(fallback_chunks, "rb") as f:
                _chunks_cache = pickle.load(f)
        return _index_cache, _chunks_cache
    except Exception as e:
        return None, None


def index_exists() -> bool:
    fallback_index = os.path.join(ROOT_DIR, "data", "faiss_index", "index.npy")
    fallback_chunks = os.path.join(ROOT_DIR, "data", "faiss_index", "chunks.pkl")
    return (os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH)) or (os.path.exists(fallback_index) and os.path.exists(fallback_chunks))


def invalidate_cache():
    """Call this after rebuilding the index."""
    global _index_cache, _chunks_cache
    _index_cache = None
    _chunks_cache = None


# ─── Retrieval ────────────────────────────────────────────────────

def retrieve(query: str, batch_id: str, index, chunks: list, top_k: int = 5) -> list:
    """
    Retrieve most relevant chunks using cosine similarity via numpy dot product.
    Batch-specific chunks are prioritised over general ones.
    """
    q_vec = embed_text(query)
    q_norm = np.linalg.norm(q_vec)
    if q_norm > 0:
        q_vec = q_vec / q_norm

    # Since index vectors are pre-normalized, dot product is cosine similarity
    scores = np.dot(index, q_vec)
    idxs = np.argsort(scores)[::-1]

    # First pass: batch-specific vs general
    batch_results = []
    general_results = []

    for idx in idxs:
        score = scores[idx]
        chunk = chunks[idx]
        entry = (float(score), chunk)
        if chunk["batch_id"] == batch_id:
            batch_results.append(entry)
        elif chunk["batch_id"] == "all":
            general_results.append(entry)

    # Combine: batch first, then general, up to top_k
    combined = batch_results + general_results
    return combined[:top_k]


# ─── Main answer function ─────────────────────────────────────────

def answer(query: str, batch_id: str = "mba_jan_26_sem1", language: str = "English", erp_id: str = None) -> dict:
    """
    Main entry point for EduBot.

    Returns dict with:
      answer       : str — the bot's response
      sources      : list[str] — source names used
      confidence   : float — 0.0 to 1.0
      escalate     : bool — True if confidence is low
      is_redirect  : bool — True if Layer 0 triggered
      erp_link     : str|None — ERP URL to redirect to
      erp_label    : str|None — Button label for the URL
    """

    # ── STEP 1: Layer 0 check ─────────────────────────────────────
    redirect = check_layer0(query)
    if redirect:
        if erp_id and erp_id in MOCK_STUDENTS:
            student = MOCK_STUDENTS[erp_id]
            personal_context = f"""=== VERIFIED ERP DATA FOR {student['name']} ===
Student: {student['name']}
ERP ID: {erp_id}
PRN: {student['prn']}
Program: {student['program']}
Batch: {student['batch']}, Semester {student['semester']}
Specialization: {student['specialization']}
Mentor: {student['mentor']}

FEES:
- Total program fee: Rs {student['fees']['total']:,}
- Paid so far: Rs {student['fees']['paid']:,}
- Outstanding: Rs {student['fees']['outstanding']:,}
- Sem 1: {student['fees']['sem1']}
- Sem 2: {student['fees']['sem2']}

ASSIGNMENTS:
- Total: {student['assignments']['total']}
- Submitted: {student['assignments']['submitted']}
- Pending: {student['assignments']['pending']}
- Pending list: {', '.join(student['assignments']['pending_list']) if student['assignments']['pending_list'] else 'None'}

EXAMINATION:
- Exam form: {student['exam']['form']}
- Admit card: {student['exam']['admit_card']}
- Exam date: {student['exam']['exam_date']}
- Result: {student['exam']['result']}
- Backlog subjects: {', '.join(student['exam']['backlog']) if student['exam']['backlog'] else 'None'}

ATTENDANCE: {student['attendance']}%
BOOKS DISPATCH: {student['books']}"""

            system_prompt = f"""You are DPU EduBot answering a personal query for an enrolled student.
             
STRICT RULES:
1. Use ONLY the verified ERP data below. Never invent numbers, dates, or details.
2. Address the student by their first name.
3. Be warm, concise, and helpful — like a kind mentor.
4. If their data shows an issue (overdue fees, pending assignments), be direct but supportive.
5. End with a clear next step where useful (e.g. "You can pay online at ERP — Payments section").
6. Respond in the same language, script, and style as the student's question (e.g. if the user asks in Hinglish/Latin-script Hindi, answer in Hinglish/Latin-script Hindi; if in Devanagari Hindi, answer in Devanagari Hindi; if in Devanagari Marathi, answer in Devanagari Marathi; if in Marathish/Latin-script Marathi, answer in Marathish/Latin-script Marathi; if in English, answer in English).

{personal_context}"""
            try:
                response = client.chat.completions.create(
                    model=CHAT_MODEL,
                    temperature=0.1,
                    max_tokens=400,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": query}
                    ]
                )
                bot_answer = response.choices[0].message.content
            except Exception as e:
                bot_answer = f"Unable to fetch personalized details: {str(e)}"
            
            return {
                "answer": bot_answer,
                "sources": ["DPU ERP Student Record"],
                "confidence": 1.0,
                "escalate": False,
                "is_redirect": False,
                "erp_link": redirect["link"],
                "erp_label": redirect["label"]
            }
        else:
            system_prompt = """You are DPU EduBot, a warm and helpful AI learning assistant.
             
STRICT RULES:
1. Rephrase the redirect message below to be warm, clear, and helpful.
2. Instruct the user to log in or select their ERP ID from the dropdown at the top of the chat page if they want to check their personal details in this chat.
3. Respond in the exact same language, script, and style as the student's query (e.g., Hinglish, Devanagari Hindi, Marathish, Devanagari Marathi, or English).

Redirect Message:
{message}"""
            try:
                response = client.chat.completions.create(
                    model=CHAT_MODEL,
                    temperature=0.1,
                    max_tokens=250,
                    messages=[
                        {"role": "system", "content": system_prompt.format(message=redirect["message"])},
                        {"role": "user",   "content": query}
                    ]
                )
                bot_answer = response.choices[0].message.content
            except Exception:
                bot_answer = redirect["message"] + "\n\n💡 **Tip:** If you want to check your personal account info directly in this chat, please select your ERP ID from the dropdown at the top of the chat page."

            return {
                "answer": bot_answer,
                "sources": [],
                "confidence": 1.0,
                "escalate": False,
                "is_redirect": True,
                "erp_link": redirect["link"],
                "erp_label": redirect["label"]
            }

    # ── STEP 2: Check index exists ────────────────────────────────
    if not index_exists():
        return {
            "answer": (
                "The knowledge base is not yet built. "
                "Please go to the Admin panel and click "
                "'Build Knowledge Base Index' to set it up."
            ),
            "sources": [],
            "confidence": 0.0,
            "escalate": True,
            "is_redirect": False,
            "erp_link": None,
            "erp_label": None
        }

    # ── STEP 3: Load index and retrieve ───────────────────────────
    index, chunks = load_index()
    if index is None:
        return {
            "answer": "Unable to load knowledge base. Please contact admin to rebuild the index.",
            "sources": [],
            "confidence": 0.0,
            "escalate": True,
            "is_redirect": False,
            "erp_link": None,
            "erp_label": None
        }

    results = retrieve(query, batch_id, index, chunks)

    if not results:
        return {
            "answer": (
                "I don't have verified information on this topic. "
                "Please contact your mentor or raise a support ticket on ERP at "
                "col5.dpuerp.in — Student Support Ticket."
            ),
            "sources": [],
            "confidence": 0.0,
            "escalate": True,
            "is_redirect": False,
            "erp_link": "https://col5.dpuerp.in/Secured/StudentCOL/StudentGrievance.aspx",
            "erp_label": "Raise Support Ticket on ERP"
        }

    # ── STEP 4: Compute confidence ────────────────────────────────
    confidence = float(np.mean([s for s, _ in results[:3]]))

    # ── STEP 5: Build context from retrieved chunks ───────────────
    context_parts = []
    for _, chunk in results:
        source_label = f"[{chunk.get('source', 'DPU Knowledge Base')}]"
        context_parts.append(f"{source_label}\n{chunk['text']}")
    context = "\n\n".join(context_parts)

    sources = list({chunk.get("source", "DPU Knowledge Base") for _, chunk in results})

    # ── STEP 6: Build strict system prompt ───────────────────────
    system_prompt = f"""You are DPU EduBot — the official AI assistant for enrolled students of
Dr. D.Y. Patil Centre for Online Learning (DPU COL).

YOUR STRICT RULES — follow these exactly, no exceptions:

1. Answer ONLY using the context provided below. Do NOT use any knowledge from your training.
2. If the answer is not clearly present in the provided context, respond with EXACTLY:
   "I don't have verified information on this. Please contact your mentor or raise a
   support ticket on ERP at col5.dpuerp.in — Student Support Ticket."
3. Do NOT guess, invent, assume, or extrapolate any information.
4. If a student asks about PERSONAL data (their specific fees paid, their attendance %, 
   their exam result, their PRN, their admit card, their assignment marks) — tell them 
   to check ERP directly. Do not try to answer from context.
5. When guiding to raise a support ticket, always mention the EXACT Category and 
   Nature of Support (e.g. Category: Accounts | Nature: Online Fee Payment Issues).
6. Respond in the same language, script, and style as the student's question (e.g. if the user asks in Hinglish/Latin-script Hindi, answer in Hinglish/Latin-script Hindi; if in Devanagari Hindi, answer in Devanagari Hindi; if in Devanagari Marathi, answer in Devanagari Marathi; if in Marathish/Latin-script Marathi, answer in Marathish/Latin-script Marathi; if in English, answer in English).
7. Be warm, concise, and helpful. Use numbered steps for processes. Use bullet points 
   for lists. Keep answers focused and specific.
8. Always end with a helpful next step or offer to clarify further.

CONTEXT FROM DPU VERIFIED KNOWLEDGE BASE:
{context}"""

    # ── STEP 7: Call GPT-4o-mini ──────────────────────────────────
    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0.1,
            max_tokens=600,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
        )
        bot_answer = response.choices[0].message.content
    except Exception as e:
        bot_answer = f"Unable to generate response: {str(e)}"
        confidence = 0.0

    return {
        "answer": bot_answer,
        "sources": sources,
        "confidence": confidence,
        "escalate": confidence < CONF_THRESHOLD,
        "is_redirect": False,
        "erp_link": None,
        "erp_label": None
    }

