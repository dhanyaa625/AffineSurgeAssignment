import requests

BASE_URL = "http://127.0.0.1:8000"

def run_demo():
    print("=== Implementation Demo ===\n")

    print("[1] Ingesting v1...")
    with open("data-20260715T084152Z-1-001/data/ct200_manual.md", "rb") as f:
        res = requests.post(f"{BASE_URL}/ingest", data={"version": "v1"}, files={"file": f})
    print(res.json())
    
    print("\n[2] Fetching v1 TOP-LEVEL nodes...")
    res = requests.get(f"{BASE_URL}/nodes/top?version=v1")
    nodes = res.json()
    print(f"Found {len(nodes)} top-level nodes in v1.")
    
    if len(nodes) < 1: return
    top_node_id = nodes[0]["id"]
    
    print(f"\n[3] Fetching specific node (ID: {top_node_id}) with children...")
    res = requests.get(f"{BASE_URL}/nodes/{top_node_id}")
    print(res.json())
    
    print("\n[4] Testing Search (Query: 'Error Codes')...")
    res = requests.get(f"{BASE_URL}/search?q=Error Codes&version=v1")
    print(f"Found {len(res.json())} matches.")
    
    print("\n[5] Creating Selection...")
    node_ids = [n["id"] for n in nodes[:2]]
    res = requests.post(f"{BASE_URL}/selections", json={"name": "test_sel", "node_ids": node_ids})
    sel_id = res.json()["selection_id"]

    print(f"\n[6] Generating Test Cases for Selection {sel_id}...")
    try:
        res = requests.post(f"{BASE_URL}/generate/{sel_id}")
        print(res.json())
    except Exception as e:
        print("Generation failed:", e)
        
    print("\n[7] Ingesting v2 (Smart Deduplication)...")
    with open("data-20260715T084152Z-1-001/data/ct200_manual_v2.md", "rb") as f:
        res = requests.post(f"{BASE_URL}/ingest", data={"version": "v2"}, files={"file": f})
    print(res.json())
    
    print(f"\n[8] Checking Staleness for Selection {sel_id}...")
    res = requests.get(f"{BASE_URL}/test-cases/{sel_id}")
    print(res.json())
    
    print("\n[9] Checking Diff for a changed node (Assuming Node 2 changed)...")
    res = requests.get(f"{BASE_URL}/nodes/2/diff")
    print(res.json())

if __name__ == "__main__":
    run_demo()
