
import json, re, math
from pathlib import Path
from collections import defaultdict
from typing import List, Dict
import numpy as np

class CareerRecommender:
    def __init__(self, json_path: Path):
        self.json_path = Path(json_path)
        self.data = json.loads(self.json_path.read_text(encoding="utf-8"))
        # Build vocab
        self.skills_vocab = sorted({s.lower() for item in self.data for s in item["skills"]})
        # Build TF vectors for careers
        self.skill_to_index = {s:i for i,s in enumerate(self.skills_vocab)}
        self.matrix = self._build_matrix()

    def _build_matrix(self):
        m = np.zeros((len(self.data), len(self.skills_vocab)), dtype=np.float32)
        for i, item in enumerate(self.data):
            for s in item["skills"]:
                idx = self.skill_to_index.get(s.lower())
                if idx is not None:
                    m[i, idx] = 1.0
        # normalize rows
        row_norms = np.linalg.norm(m, axis=1, keepdims=True)
        row_norms[row_norms==0] = 1.0
        return m / row_norms

    def _vectorize_skills(self, skills: List[str]):
        v = np.zeros((len(self.skills_vocab),), dtype=np.float32)
        for raw in skills:
            s = raw.lower().strip()
            # fuzzy: accept partial matches
            for vocab in self.skills_vocab:
                if s == vocab or (len(s) > 2 and s in vocab):
                    v[self.skill_to_index[vocab]] = 1.0
        n = np.linalg.norm(v)
        if n == 0:
            return v
        return v / n

    def recommend_by_skills(self, skills: List[str], topn=10):
        if not isinstance(skills, list):
            skills = [skills]
        q = self._vectorize_skills(skills)
        if np.linalg.norm(q) == 0:
            return []
        sims = self.matrix.dot(q)
        idxs = np.argsort(-sims)[:topn]
        out = []
        for i in idxs:
            item = self.data[int(i)]
            # top skills to learn = the skills of career not present in query
            query_set = {s.lower() for s in skills}
            learn = [s for s in item["skills"] if all(qs not in s.lower() for qs in query_set)]
            out.append({
                "career": item["career"],
                "match": float(sims[int(i)]),
                "top_skills": learn[:10],
                "links": item.get("links", [])[:3]
            })
        return out

    def suggest(self, q: str):
        if not q:
            return {"skills": [], "careers": []}
        ql = q.lower()
        skills = sorted({s for s in self.skills_vocab if ql in s})[:15]
        careers = sorted({d["career"] for d in self.data if ql in d["career"].lower()})[:15]
        return {"skills": skills, "careers": careers}

    def skills_for_career(self, name: str):
        if not name:
            return []
        nl = name.lower()
        for d in self.data:
            if nl in d["career"].lower():
                return d["skills"]
        return []
