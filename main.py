import sqlite3
import hashlib
import os
import difflib
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import google.generativeai as genai

app = FastAPI()

DB_FILE = "app_v2.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            logical_path TEXT,
            parent_id INTEGER,
            heading TEXT,
            level INTEGER,
            content TEXT,
            content_hash TEXT,
            versions TEXT,
            FOREIGN KEY(parent_id) REFERENCES nodes(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            node_ids TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            selection_id INTEGER,
            output_text TEXT,
            FOREIGN KEY(selection_id) REFERENCES selections(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()

class ParsedNode:
    def __init__(self, heading: str, level: int):
        self.heading = heading
        self.level = level
        self.content_lines = []
        self.parent = None
        self.logical_path = ""
        self.db_id = None

def parse_markdown_to_nodes(content: str) -> List[ParsedNode]:
    lines = content.split('\n')
    nodes = []
    
    root_node = ParsedNode("Document Root", 0)
    root_node.logical_path = "Document Root"
    nodes.append(root_node)
    
    stack = [root_node]
    heading_counts = {}

    for line in lines:
        if line.startswith("#"):
            parts = line.split(" ", 1)
            level = len(parts[0])
            heading = parts[1].strip() if len(parts) > 1 else ""
            
            # Pop stack until we find a parent with a strictly smaller level
            # This handles skipping levels (e.g., H2 -> H4 correctly parents H4 under H2)
            while stack and stack[-1].level >= level:
                stack.pop()
                
            parent = stack[-1] if stack else root_node
            
            new_node = ParsedNode(heading, level)
            new_node.parent = parent
            
            # Calculate logical path with deduplication
            base_path = f"{parent.logical_path}/{heading}"
            heading_counts[base_path] = heading_counts.get(base_path, 0) + 1
            if heading_counts[base_path] > 1:
                new_node.logical_path = f"{base_path} [{heading_counts[base_path]}]"
            else:
                new_node.logical_path = base_path
                
            nodes.append(new_node)
            stack.append(new_node)
        else:
            if stack:
                stack[-1].content_lines.append(line)
                
    return nodes

@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...), version: str = Form("v1")):
    content = (await file.read()).decode("utf-8")
    parsed_nodes = parse_markdown_to_nodes(content)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # We must insert top-down to resolve parent_ids correctly
    # Since parsed_nodes is created in-order, parent is always processed before child
    newly_ingested = 0
    updated_versions = 0
    
    for p_node in parsed_nodes:
        body = "\n".join(p_node.content_lines).strip()
        c_hash = get_hash(p_node.heading + body)
        parent_db_id = p_node.parent.db_id if p_node.parent else None
        
        # Check if this exact logical node already exists
        c.execute("SELECT id, content_hash, versions FROM nodes WHERE logical_path = ?", (p_node.logical_path,))
        existing_rows = c.fetchall()
        
        matched_existing = False
        for row in existing_rows:
            db_id, db_hash, db_versions = row
            # If same hash, it's semantically unchanged. Just append the version if not present.
            if db_hash == c_hash:
                matched_existing = True
                p_node.db_id = db_id
                versions_list = db_versions.split(",")
                if version not in versions_list:
                    versions_list.append(version)
                    new_versions = ",".join(versions_list)
                    c.execute("UPDATE nodes SET versions = ? WHERE id = ?", (new_versions, db_id))
                    updated_versions += 1
                break
                
        if not matched_existing:
            # Hash changed (or completely new node). Create a new row.
            c.execute(
                "INSERT INTO nodes (logical_path, parent_id, heading, level, content, content_hash, versions) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (p_node.logical_path, parent_db_id, p_node.heading, p_node.level, body, c_hash, version)
            )
            p_node.db_id = c.lastrowid
            newly_ingested += 1
            
    conn.commit()
    conn.close()
    
    return {"message": f"Successfully ingested. New nodes: {newly_ingested}. Updated existing nodes: {updated_versions}."}

@app.get("/nodes")
def get_nodes(version: str = "v1"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, parent_id, logical_path, heading, level FROM nodes WHERE versions LIKE ?", (f"%{version}%",))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "parent_id": r[1], "logical_path": r[2], "heading": r[3], "level": r[4]} for r in rows]

@app.get("/nodes/top")
def get_top_nodes(version: str = "v1"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, logical_path, heading FROM nodes WHERE parent_id IS NULL AND versions LIKE ?", (f"%{version}%",))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "logical_path": r[1], "heading": r[2]} for r in rows]

@app.get("/nodes/{node_id}")
def get_node(node_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT logical_path, heading, content, content_hash, versions FROM nodes WHERE id = ?", (node_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Node not found")
        
    c.execute("SELECT id, heading FROM nodes WHERE parent_id = ?", (node_id,))
    children = c.fetchall()
    conn.close()
    
    return {
        "id": node_id,
        "logical_path": row[0],
        "heading": row[1],
        "content": row[2],
        "content_hash": row[3],
        "versions": row[4],
        "children": [{"id": ch[0], "heading": ch[1]} for ch in children]
    }

@app.get("/search")
def search_nodes(q: str, version: str = "v1"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = f"%{q}%"
    c.execute("SELECT id, logical_path, heading FROM nodes WHERE (heading LIKE ? OR content LIKE ?) AND versions LIKE ?", (query, query, f"%{version}%"))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "logical_path": r[1], "heading": r[2]} for r in rows]

@app.get("/nodes/{node_id}/diff")
def get_node_diff(node_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT logical_path, content, versions FROM nodes WHERE id = ?", (node_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Node not found")
        
    logical_path, content, versions = row
    
    # Find all versions of this logical path
    c.execute("SELECT id, content, versions FROM nodes WHERE logical_path = ? ORDER BY id ASC", (logical_path,))
    all_versions = c.fetchall()
    conn.close()
    
    if len(all_versions) <= 1:
        return {"message": "No other versions of this node exist to diff against."}
        
    # Simply diff the first version's content vs the last version's content for demonstration
    old_content = all_versions[0][1].splitlines()
    new_content = all_versions[-1][1].splitlines()
    
    diff = list(difflib.unified_diff(old_content, new_content, fromfile="v1", tofile="latest", lineterm=""))
    return {"diff": diff}

class SelectionRequest(BaseModel):
    name: str
    node_ids: List[int]

@app.post("/selections")
def create_selection(req: SelectionRequest):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    node_ids_str = ",".join(map(str, req.node_ids))
    c.execute("INSERT INTO selections (name, node_ids) VALUES (?, ?)", (req.name, node_ids_str))
    sel_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"selection_id": sel_id, "name": req.name}

@app.post("/generate/{selection_id}")
def generate_test_cases(selection_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT node_ids FROM selections WHERE id = ?", (selection_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Selection not found")
    
    node_ids = row[0].split(",")
    
    combined_text = ""
    for nid in node_ids:
        c.execute("SELECT heading, content FROM nodes WHERE id = ?", (int(nid),))
        node = c.fetchone()
        if node:
            combined_text += f"\n\n{node[0]}\n{node[1]}"
            
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
         conn.close()
         return {"error": "GEMINI_API_KEY not set"}
         
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3-flash-preview')
    prompt = f"Based on this text, generate 3 QA test cases. Return ONLY a valid JSON array of objects with keys 'test_case', 'expected_result'. \nText: {combined_text}"
    
    try:
        response = model.generate_content(prompt)
        output_text = response.text
    except Exception as e:
        conn.close()
        return {"error": str(e)}
        
    c.execute("INSERT INTO test_cases (selection_id, output_text) VALUES (?, ?)", (selection_id, output_text))
    test_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"test_case_id": test_id, "output": output_text}

@app.get("/test-cases/{selection_id}")
def get_test_cases(selection_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT output_text FROM test_cases WHERE selection_id = ?", (selection_id,))
    test_rows = c.fetchall()
    
    # Staleness check using Logical Path and Hash
    c.execute("SELECT node_ids FROM selections WHERE id = ?", (selection_id,))
    sel_row = c.fetchone()
    is_stale = False
    
    if sel_row:
        node_ids = sel_row[0].split(",")
        for nid in node_ids:
            c.execute("SELECT logical_path, content_hash FROM nodes WHERE id = ?", (int(nid),))
            v1_node = c.fetchone()
            if v1_node:
                logical_path, v1_hash = v1_node
                # Look for the latest node with the same logical path
                c.execute("SELECT content_hash FROM nodes WHERE logical_path = ? ORDER BY id DESC LIMIT 1", (logical_path,))
                latest_node = c.fetchone()
                if latest_node and latest_node[0] != v1_hash:
                    is_stale = True
                    break
                    
    conn.close()
    return {
        "is_stale": is_stale,
        "test_cases": [r[0] for r in test_rows]
    }
