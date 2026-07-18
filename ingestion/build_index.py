"""
DPU EduBot — Build FAISS Index from knowledge_base.json
Run this once after setup: python ingestion/build_index.py
"""

import json
import os
import sys
import pickle
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL = "text-embedding-3-small"
import tempfile
INDEX_PATH = os.path.join(tempfile.gettempdir(), "faiss_index", "index.npy")
CHUNKS_PATH = os.path.join(tempfile.gettempdir(), "faiss_index", "chunks.pkl")
KB_PATH = "data/knowledge_base.json"
USE_MOCK = False

def embed_text(text: str) -> np.ndarray:
    """Get embedding vector for a text string, falling back to mock vector on error."""
    global USE_MOCK
    if not USE_MOCK:
        try:
            res = client.embeddings.create(input=[text], model=EMBED_MODEL, timeout=5.0)
            return np.array(res.data[0].embedding, dtype="float32")
        except Exception as e:
            print(f"\n[Warning] API call failed: {e}. Switching to offline fallback embeddings.")
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




def build_chunks_from_kb(kb: dict) -> list:
    """Convert knowledge base JSON into flat list of text chunks."""
    chunks = []

    # ── Layer 1: All FAQs ──────────────────────────────────────────
    print("  Processing Layer 1 FAQs...")
    for cat_key, cat_data in kb["layer_1_faqs"].items():
        for faq in cat_data["faqs"]:
            text = f"Q: {faq['q']}\nA: {faq['a']}"
            chunks.append({
                "text": text,
                "source": "DPU Official FAQ",
                "category": cat_key,
                "category_label": cat_data["label"],
                "batch_id": "all",
                "layer": "layer_1",
                "tags": faq.get("tags", [])
            })

    # ── Layer 2: Batch-specific data ───────────────────────────────
    print("  Processing Layer 2 Batch data...")
    for batch_id, batch in kb["layer_2_batch_specific"].items():
        label = batch["label"]

        # Subjects
        valid_subjects = [
            s for s in batch["subjects"]
            if "TBD" not in s["code"] and "ADMIN" not in s["code"]
        ]
        if valid_subjects:
            subj_list = ", ".join([f"{s['code']} - {s['name']}" for s in valid_subjects])
            chunks.append({
                "text": f"Subjects for {label} (Semester {batch['semester']}): {subj_list}",
                "source": label,
                "category": "subjects",
                "batch_id": batch_id,
                "layer": "layer_2",
                "tags": ["subjects", "courses", "sem1"]
            })

        # Fee structure
        fees = batch.get("fee_structure", {})
        if "sem1" in fees:
            fee_text = (
                f"Fee structure for {label}: "
                f"Semester 1 = Rs {fees['sem1']:,} | "
                f"Semester 2 = Rs {fees['sem2']:,} | "
                f"Semester 3 = Rs {fees['sem3']:,} | "
                f"Semester 4 = Rs {fees['sem4']:,} | "
                f"Total program fee = Rs {fees['total']:,}. {fees.get('note','')}"
            )
            chunks.append({
                "text": fee_text,
                "source": label,
                "category": "fees",
                "batch_id": batch_id,
                "layer": "layer_2",
                "tags": ["fees", "fee structure", "amount"]
            })

        # Important dates
        dates = batch.get("important_dates", {})
        date_parts = []
        for k, v in dates.items():
            if k != "note" and v and "TBD" not in str(v) and "ADMIN" not in str(v):
                date_parts.append(f"{k.replace('_', ' ')}: {v}")
        if date_parts:
            date_text = f"Key dates for {label}: " + " | ".join(date_parts)
            chunks.append({
                "text": date_text,
                "source": label,
                "category": "dates",
                "batch_id": batch_id,
                "layer": "layer_2",
                "tags": ["dates", "calendar", "schedule", "exam dates"]
            })

        # Specializations
        specs = batch.get("specializations", [])
        if specs:
            spec_text = (
                f"Specializations available for {label}: "
                + ", ".join(specs)
            )
            chunks.append({
                "text": spec_text,
                "source": label,
                "category": "specializations",
                "batch_id": batch_id,
                "layer": "layer_2",
                "tags": ["specialization", "options"]
            })

        # ERP Links
        erp = batch.get("erp_links", {})
        if erp:
            erp_text = (
                f"ERP portal links for {label}: "
                f"Assignments: {erp.get('assignments','')} | "
                f"Payments: {erp.get('payments','')} | "
                f"Examination: {erp.get('examination','')} | "
                f"Support Ticket: {erp.get('support_ticket','')} | "
                f"LMS: {erp.get('lms','')}"
            )
            chunks.append({
                "text": erp_text,
                "source": label,
                "category": "erp_links",
                "batch_id": batch_id,
                "layer": "layer_2",
                "tags": ["links", "erp portal", "url"]
            })

    # ── Support ticket taxonomy ────────────────────────────────────
    print("  Processing Support Ticket Taxonomy...")
    for category, subtypes in kb["support_ticket_taxonomy"].items():
        for subtype in subtypes:
            text = (
                f"To raise a support ticket for '{subtype}': "
                f"Go to ERP — Student Support Ticket — "
                f"Support Category: {category} — "
                f"Nature of Support: {subtype}"
            )
            chunks.append({
                "text": text,
                "source": "DPU ERP Support System",
                "category": "support_ticket",
                "batch_id": "all",
                "layer": "layer_1",
                "tags": ["ticket", category.lower(), subtype.lower()]
            })

    # ── Layer 3: Website topics ────────────────────────────────────
    print("  Processing Layer 3 Website data...")
    for topic in kb["layer_3_website"]["key_topics"]:
        chunks.append({
            "text": topic,
            "source": "dypatilonline.com",
            "category": "website",
            "batch_id": "all",
            "layer": "layer_3",
            "tags": ["website", "general", "program info"]
        })

    # ── Layer 4: Uploaded batch documents ───────────────────────────
    print("  Processing Layer 4 Uploaded batch documents...")
    import tempfile
    uploads_dir = os.path.join(tempfile.gettempdir(), "batch_uploads")
    if os.path.exists(uploads_dir):
        for f in os.listdir(uploads_dir):
            if f.endswith(".pkl"):
                pkl_path = os.path.join(uploads_dir, f)
                try:
                    with open(pkl_path, "rb") as pf:
                        uploaded_chunks = pickle.load(pf)
                        chunks.extend(uploaded_chunks)
                        print(f"    Loaded {len(uploaded_chunks)} chunks from {f}")
                except Exception as e:
                    print(f"    Error loading {f}: {e}")

    return chunks


def build_index():
    """Main function to build and save the knowledge base index."""
    print("\n[Build] Building DPU EduBot Index...")

    # 1. Load pre-built default index and chunks
    try:
        default_vectors = np.load("data/faiss_index/index.npy")
        with open("data/faiss_index/chunks.pkl", "rb") as f:
            default_chunks = pickle.load(f)
        print(f"  Loaded pre-built base index with {len(default_chunks)} chunks.")
    except Exception as e:
        print(f"  Failed to load base index: {e}")
        default_vectors = None
        default_chunks = []

    # 2. Get uploaded chunks that need to be appended
    import tempfile
    uploads_dir = os.path.join(tempfile.gettempdir(), "batch_uploads")
    uploaded_chunks = []
    if os.path.exists(uploads_dir):
        for f in os.listdir(uploads_dir):
            if f.endswith(".pkl"):
                pkl_path = os.path.join(uploads_dir, f)
                try:
                    with open(pkl_path, "rb") as pf:
                        uploaded_chunks.extend(pickle.load(pf))
                except Exception as e:
                    print(f"    Error loading uploaded chunks from {f}: {e}")
    print(f"  Loaded {len(uploaded_chunks)} uploaded chunks to index.")

    # 3. If there are no uploaded chunks and we have the default index, just copy it to temp
    if not uploaded_chunks and default_vectors is not None:
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        np.save(INDEX_PATH, default_vectors)
        with open(CHUNKS_PATH, "wb") as f:
            pickle.dump(default_chunks, f)
        print("[Success] Reused base index (no uploads).")
        return len(default_chunks)

    # 4. Generate vectors for uploaded chunks only
    uploaded_vectors = []
    if uploaded_chunks:
        print(f"  Embedding {len(uploaded_chunks)} uploaded chunks...")
        for i, chunk in enumerate(uploaded_chunks):
            vec = embed_text(chunk["text"])
            uploaded_vectors.append(vec)
        
        uploaded_vectors_np = np.array(uploaded_vectors, dtype="float32")
        # Normalize
        norms = np.linalg.norm(uploaded_vectors_np, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        uploaded_vectors_np = uploaded_vectors_np / norms

    # 5. Combine base vectors/chunks and uploaded vectors/chunks
    if default_vectors is not None:
        if uploaded_chunks:
            combined_vectors = np.vstack([default_vectors, uploaded_vectors_np])
            combined_chunks = default_chunks + uploaded_chunks
        else:
            combined_vectors = default_vectors
            combined_chunks = default_chunks
    else:
        # Fall back to rebuilding everything if base index failed to load
        with open(KB_PATH, encoding="utf-8") as f:
            kb = json.load(f)
        combined_chunks = build_chunks_from_kb(kb) + uploaded_chunks
        print(f"  Fallback: Embedding all {len(combined_chunks)} chunks...")
        combined_vectors_list = [embed_text(c["text"]) for c in combined_chunks]
        combined_vectors = np.array(combined_vectors_list, dtype="float32")
        norms = np.linalg.norm(combined_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        combined_vectors = combined_vectors / norms

    # 6. Save the combined index
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    np.save(INDEX_PATH, combined_vectors)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(combined_chunks, f)

    print(f"\n[Success] Index built successfully!")
    print(f"   Total chunks indexed: {len(combined_chunks)}")
    return len(combined_chunks)


if __name__ == "__main__":
    count = build_index()
    if count > 0:
        print(f"\n[Ready] DPU EduBot is ready with {count} knowledge chunks!")
        print("   Local runner setup is ready.")

