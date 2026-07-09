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

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
CONF_THRESHOLD = 0.50
INDEX_PATH = "data/faiss_index/index.npy"
CHUNKS_PATH = "data/faiss_index/chunks.pkl"
KB_PATH = "data/knowledge_base.json"

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
        _index_cache = np.load(INDEX_PATH)
        with open(CHUNKS_PATH, "rb") as f:
            _chunks_cache = pickle.load(f)
        return _index_cache, _chunks_cache
    except Exception as e:
        return None, None


def index_exists() -> bool:
    return os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH)


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

def answer(query: str, batch_id: str = "mba_jan_26_sem1", language: str = "English") -> dict:
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
        return {
            "answer": redirect["message"],
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
6. Respond in {language}.
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
