# 🎓 DPU EduBot

Official AI-powered learning assistant for enrolled students of  
**Dr. D.Y. Patil Centre for Online Learning (DPU COL)**

---

## ⚡ Quick Setup — Step by Step

### STEP 1 — Open project in VS Code

1. Unzip the `dpu-edubot.zip` file you downloaded
2. Open VS Code
3. Go to **File → Open Folder** → select the `dpu-edubot-final` folder
4. Open the integrated terminal: **Terminal → New Terminal** (or press `` Ctrl + ` ``)

---

### STEP 2 — Create virtual environment

In the VS Code terminal, run:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

✅ You should see `(venv)` appear at the start of your terminal prompt.

---

### STEP 3 — Install all dependencies

```bash
pip install -r requirements.txt
```

This installs: Streamlit, OpenAI, FAISS, LangChain, pdfplumber, and all other packages.  
It takes about 2-3 minutes the first time.

---

### STEP 4 — Set up your API key

1. In VS Code, find the file `.env.example` in the file explorer
2. **Rename it to `.env`** (remove the `.example` part)
3. Open `.env` and replace the placeholder with your actual OpenAI API key:

```
OPENAI_API_KEY=sk-your-actual-key-here
ADMIN_PASSWORD=admin@dpu2026
FACULTY_PASSWORD=faculty@dpu2026
```

> ⚠️ **Important:** Never share your `.env` file or push it to GitHub.

---

### STEP 5 — Build the Knowledge Base Index

```bash
python ingestion/build_index.py
```

This will:
- Read all 113 verified FAQs from `data/knowledge_base.json`
- Read batch-specific data (MBA Jan 26 subjects, fee structure, etc.)
- Embed everything using OpenAI
- Save the FAISS vector index to `data/faiss_index/`

Expected output:
```
🔨 Building DPU EduBot FAISS index...
  Processing Layer 1 FAQs...
  Processing Layer 2 Batch data...
  Processing Layer 3 Website data...
  Total chunks to embed: 145
  Embedding chunks...
  Progress: 10/145 chunks embedded
  ...
✅ Index built successfully!
   Chunks indexed: 145
🎓 DPU EduBot is ready!
```

This takes about **1-2 minutes** and costs a small amount from your OpenAI API credits.

---

### STEP 6 — Run the app!

```bash
streamlit run app/main.py
```

The app will open automatically in your browser at **http://localhost:8501**

---

## 🎭 Three Role Views

| Role | Access | Password |
|------|--------|----------|
| **Student** | Chat interface, batch selector, language toggle | No password |
| **Admin** | Knowledge base manager, batch document upload, index builder | `admin@dpu2026` |
| **Faculty** | Batch reference, material upload, query trends | `faculty@dpu2026` |

> Change passwords in your `.env` file before sharing with others.

---

## 🧠 How it works — Zero Hallucination Architecture

**Every query follows this priority chain:**

```
Layer 0: Is this about personal data (attendance, fees, result, PRN)?
  → YES: Immediately redirect to correct ERP URL. No LLM used.
  → NO: Continue to Layer 1

Layer 1: Is this covered in the 113 verified FAQs?
  → Search FAISS index for matching FAQ chunks

Layer 2: Is this batch-specific (subjects, dates, fees)?
  → Search batch-specific data for MBA Jan 26 / BBA Jan 26

Layer 3: Is this a general program/eligibility question?
  → Search website scraped data

If no match found → "I don't have verified information on this. Please contact your mentor."
```

The bot **never guesses** and **never invents** information.

---

## 📁 Project Structure

```
dpu-edubot-final/
│
├── app/
│   └── main.py              ← Streamlit app (all 3 role views)
│
├── rag/
│   └── pipeline.py          ← Zero-hallucination RAG engine
│
├── ingestion/
│   ├── build_index.py       ← Build FAISS index from knowledge_base.json
│   └── parse_docs.py        ← Parse PDF / DOCX / Excel uploads
│
├── data/
│   ├── knowledge_base.json  ← Complete verified knowledge base
│   ├── faiss_index/         ← Auto-generated after Step 5
│   └── batch_uploads/       ← Upload slot for batch PDFs
│
├── .env                     ← Your API key (you create this in Step 4)
├── .env.example             ← Template
├── .gitignore               ← Keeps .env and index off GitHub
├── requirements.txt         ← All Python dependencies
└── README.md                ← This file
```

---

## 📋 Adding New Batch Documents

1. Open the app → switch to **Admin** role
2. Enter admin password
3. Under **Upload Batch Document**, select:
   - Batch name
   - Document type (academic_calendar, exam_dates, etc.)
   - Upload your PDF/DOCX/Excel
4. Click **Index Document**
5. Click **Build / Rebuild Knowledge Base Index**

The new content will be searchable immediately.

---

## 🚀 Deploying to Streamlit Cloud

```bash
# 1. Push to GitHub (private repo)
git init
git add .
git commit -m "DPU EduBot v1"
git remote add origin https://github.com/YOUR_USERNAME/dpu-edubot.git
git push -u origin main

# 2. Go to share.streamlit.io
# 3. New app → select your repo → main file: app/main.py
# 4. Advanced settings → Secrets → add:
#    OPENAI_API_KEY = "sk-..."
#    ADMIN_PASSWORD = "your_password"
#    FACULTY_PASSWORD = "your_password"
# 5. Deploy!

# 6. After deploy, open Admin panel → Build Knowledge Base Index
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: faiss` | Run `pip install faiss-cpu` |
| `OpenAI API key not set` | Check your `.env` file has `OPENAI_API_KEY=sk-...` |
| `Index not found` | Run `python ingestion/build_index.py` |
| `streamlit: command not found` | Make sure venv is activated: `venv\Scripts\activate` |
| App opens but chat doesn't work | Check admin panel — is the index shown as ✅ Ready? |

---

## 📞 Support

For issues with the chatbot:  
Contact the development team or raise a support ticket on ERP at  
https://col5.dpuerp.in/Secured/StudentCOL/StudentGrievance.aspx

---

*DPU EduBot · Built for Dr. D.Y. Patil Centre for Online Learning*
