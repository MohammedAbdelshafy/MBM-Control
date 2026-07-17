import json
import os
import re
import math
from datetime import datetime
from collections import defaultdict, Counter

MEMORY_BASE = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Memory"
INDEX_FILE = os.path.join(MEMORY_BASE, "MemoryIndex.json")
GRAPH_FILE = os.path.join(MEMORY_BASE, "MemoryGraph.json")

class MemoryManager:
    def __init__(self):
        self.index_data = self._load_json(INDEX_FILE, {"version": "2.0", "entries": {}})
        self.graph_data = self._load_json(GRAPH_FILE, {"version": "2.0", "nodes": {}, "edges": []})
        self.stop_words = set(["the", "and", "a", "an", "is", "in", "it", "of", "to", "for", "with", "on", "as", "at", "by", "this"])

    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return default
        return default

    def _save_json(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _tokenize(self, text):
        text = text.lower()
        words = re.findall(r'\b[a-z0-9]+\b', text)
        return [w for w in words if w not in self.stop_words]

    def add_memory(self, category, title, content, tags=None, related_to=None):
        if not tags: tags = []
        if not related_to: related_to = []
        
        # Sanitize title for filename
        safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)
        file_name = f"{safe_title}.md"
        file_path = os.path.join(MEMORY_BASE, category, file_name)
        
        # Ensure category directory exists
        os.makedirs(os.path.join(MEMORY_BASE, category), exist_ok=True)
        
        # Write markdown content
        full_content = f"# {title}\n\n**Tags:** {', '.join(tags)}\n\n{content}"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
            
        # Update Index
        tokens = self._tokenize(full_content)
        term_freqs = dict(Counter(tokens))
        
        memory_id = f"{category}/{file_name}"
        self.index_data["entries"][memory_id] = {
            "title": title,
            "category": category,
            "path": file_path,
            "tags": tags,
            "term_freqs": term_freqs,
            "total_terms": len(tokens),
            "timestamp": datetime.now().isoformat()
        }
        self.index_data["last_updated"] = datetime.now().isoformat()
        self._save_json(INDEX_FILE, self.index_data)
        
        # Update Graph
        self.graph_data["nodes"][memory_id] = {"title": title, "category": category}
        for rel in related_to:
            self.graph_data["edges"].append({
                "source": memory_id,
                "target": rel,
                "type": "related_to"
            })
        self._save_json(GRAPH_FILE, self.graph_data)
        
        print(f"[+] Memory saved: {memory_id}")
        return memory_id

    def search(self, query, top_k=5):
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
            
        # Calculate IDF
        num_docs = len(self.index_data["entries"])
        if num_docs == 0:
            return []
            
        doc_freqs = defaultdict(int)
        for doc_id, data in self.index_data["entries"].items():
            for token in set(data.get("term_freqs", {}).keys()):
                doc_freqs[token] += 1
                
        scores = {}
        for doc_id, data in self.index_data["entries"].items():
            score = 0
            doc_tf = data.get("term_freqs", {})
            doc_len = data.get("total_terms", 1)
            
            for token in query_tokens:
                if token in doc_tf:
                    tf = doc_tf[token] / doc_len
                    idf = math.log((num_docs + 1) / (1 + doc_freqs[token])) + 1.0
                    score += tf * idf
                    
            if score > 0:
                # Add tag boost
                tags_str = " ".join(data.get("tags", [])).lower()
                for token in query_tokens:
                    if token in tags_str:
                        score *= 1.5 
                scores[doc_id] = score
                
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for doc_id, score in ranked[:top_k]:
            data = self.index_data["entries"][doc_id]
            results.append({
                "id": doc_id,
                "title": data["title"],
                "path": data["path"],
                "score": score
            })
            
        return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MBM Enterprise Memory Manager")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--test", action="store_true", help="Run integration test")
    
    args = parser.parse_args()
    
    manager = MemoryManager()
    
    if args.test:
        print("[*] Running Integration Test...")
        mid1 = manager.add_memory("Lessons", "API Rate Limiting", "We encountered HTTP 429 errors when pulling leads from Dallas Open Data API. We implemented exponential backoff in the evidence collector.", tags=["engineering", "api", "dallas"])
        mid2 = manager.add_memory("Campaigns", "Dallas Distressed Q3", "Targeting high weeds and substandard structures. Yields are around 4% conversion.", tags=["sales", "dallas", "conversion"])
        
        print("[*] Searching for 'API timeout issues'...")
        res = manager.search("API timeout issues")
        for r in res:
            print(f" -> {r['title']} (Score: {r['score']:.4f})")
            
        print("[*] Test Complete.")
        
    elif args.search:
        print(f"[*] Searching for: '{args.search}'")
        res = manager.search(args.search)
        if not res:
            print("[-] No results found.")
        else:
            for i, r in enumerate(res):
                print(f"{i+1}. {r['title']} (Score: {r['score']:.4f})")
                print(f"   Path: {r['path']}")
