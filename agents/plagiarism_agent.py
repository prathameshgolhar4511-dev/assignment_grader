"""
plagiarism_agent.py
Detects suspicious similarity between submissions in the same batch.

Code:  normalizes each submission's AST (strips variable/function names,
       comments, formatting) then compares normalized token streams with
       difflib.SequenceMatcher. Catches "renamed variables" style copying
       that a naive text diff would miss.

Math:  compares the free-text "work shown" between submissions using
       simple TF-IDF cosine similarity (no sklearn dependency — implemented
       with stdlib only for portability).
"""

import ast
import difflib
import math
from collections import Counter
from itertools import combinations


class PlagiarismAgent:
    name = "PlagiarismAgent"
    CODE_THRESHOLD = 0.80     # similarity above this => flagged
    TEXT_THRESHOLD = 0.75

    # ---------------- Code ----------------
    def _normalize_code(self, code_str: str) -> str:
        """Rename all identifiers to generic placeholders so copy+rename
        cheating still shows up as near-identical structure."""
        try:
            tree = ast.parse(code_str)
        except SyntaxError:
            return code_str  # fall back to raw text if it doesn't even parse

        name_map = {}
        counter = [0]

        class Normalizer(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id not in name_map:
                    counter[0] += 1
                    name_map[node.id] = f"VAR{counter[0]}"
                node.id = name_map[node.id]
                return node

            def visit_FunctionDef(self, node):
                if node.name not in name_map:
                    counter[0] += 1
                    name_map[node.name] = f"FUNC{counter[0]}"
                node.name = name_map[node.name]
                self.generic_visit(node)
                return node

        normalized_tree = Normalizer().visit(tree)
        return ast.dump(normalized_tree)

    def compare_code_batch(self, submissions: dict) -> list:
        """
        submissions: {student_id: code_str}
        Returns list of {"pair": (a, b), "similarity": float, "flagged": bool}
        """
        normalized = {sid: self._normalize_code(code) for sid, code in submissions.items()}
        flags = []
        for (a, code_a), (b, code_b) in combinations(normalized.items(), 2):
            ratio = difflib.SequenceMatcher(None, code_a, code_b).ratio()
            flags.append({
                "pair": (a, b),
                "similarity": round(ratio, 3),
                "flagged": ratio >= self.CODE_THRESHOLD,
            })
        return sorted(flags, key=lambda x: -x["similarity"])

    # ---------------- Math / text ----------------
    def _tfidf_vector(self, text: str, idf: dict) -> Counter:
        tokens = text.lower().split()
        tf = Counter(tokens)
        return Counter({t: tf[t] * idf.get(t, 0) for t in tf})

    def _cosine(self, v1: Counter, v2: Counter) -> float:
        common = set(v1) & set(v2)
        dot = sum(v1[t] * v2[t] for t in common)
        n1 = math.sqrt(sum(v ** 2 for v in v1.values()))
        n2 = math.sqrt(sum(v ** 2 for v in v2.values()))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def compare_text_batch(self, submissions: dict) -> list:
        """submissions: {student_id: work_text}"""
        docs = list(submissions.values())
        n_docs = len(docs) or 1
        df = Counter()
        for doc in docs:
            for tok in set(doc.lower().split()):
                df[tok] += 1
        idf = {t: math.log(n_docs / (1 + df[t])) + 1 for t in df}

        vectors = {sid: self._tfidf_vector(text, idf) for sid, text in submissions.items()}
        flags = []
        for (a, va), (b, vb) in combinations(vectors.items(), 2):
            sim = round(self._cosine(va, vb), 3)
            flags.append({"pair": (a, b), "similarity": sim, "flagged": sim >= self.TEXT_THRESHOLD})
        return sorted(flags, key=lambda x: -x["similarity"])
