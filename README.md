# Internship Assignment
This is a functional implementation of the CardioTrack CT-200 parsing and test-case generation assignment. 

## Tech Stack
- **FastAPI**: Backend framework.
- **SQLite**: Raw SQL database without ORM (for simplicity).
- **Python**: Core language.
- **Google Gemini**: LLM provider for test generation.

## Setup Instructions

1. **Install Python Requirements:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set the Gemini API Key:**
   - Windows (PowerShell): `$env:GEMINI_API_KEY="your_api_key_here"`

3. **Run the Server:**
   ```bash
   python -m uvicorn main:app --reload
   ```
   The API will be accessible at `http://127.0.0.1:8000/docs` via Swagger UI.

## End-to-End Flow (How to Test)

1. **Ingest v1:**
   Use the `POST /ingest` endpoint to upload `data/ct200_manual.md` with version `v1`.

2. **Check Nodes:**
   Use `GET /nodes?version=v1` to verify ingestion. Copy a few `id`s.

3. **Create a Selection:**
   Use `POST /selections` with a body like `{"name": "test_sel", "node_ids": [1, 2]}`.

4. **Generate QA Cases:**
   Use `POST /generate/{selection_id}`. This will call Gemini and save the JSON output.

5. **Ingest v2:**
   Use `POST /ingest` to upload `data/ct200_manual_v2.md` with version `v2`.

6. **Check Staleness:**
   Use `GET /test-cases/{selection_id}`. Since the content has changed for some v2 nodes compared to v1, the `is_stale` flag will be accurately reflected if the selection contains changed nodes.
