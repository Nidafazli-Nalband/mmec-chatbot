"""Simple TF-IDF search index for local college pages.

Usage:
- Run fetch_mmec.py to populate data/college_info/site_pages.json
- Then call build_index() which creates data/college_info/index.pkl
- Use search(query, top_k=3) to get best matching snippets
"""
import os
import json
import pickle
from typing import List, Optional, Tuple

INDEX_PATH = os.path.join('data', 'college_info', 'index.pkl')
PAGES_PATH = os.path.join('data', 'college_info', 'site_pages.json')

# Lazy imports to avoid hard dependencies during import time
def _ensure_sklearn():
    try:
        import sklearn
        return True
    except Exception:
        return False


def build_index():
    """Build TF-IDF matrix from site_pages.json and store vectorizer+matrix+pages."""
    if not _ensure_sklearn():
        raise RuntimeError('scikit-learn is required to build the index. Install with: pip install scikit-learn')
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np

    if not os.path.exists(PAGES_PATH):
        raise FileNotFoundError(f"Pages file not found: {PAGES_PATH}. Run fetch_mmec.py first.")
    with open(PAGES_PATH, 'r', encoding='utf-8') as f:
        pages = json.load(f)
    docs = [p.get('text','') for p in pages]
    urls = [p.get('url','') for p in pages]

    vec = TfidfVectorizer(stop_words='english', max_features=20000)
    X = vec.fit_transform(docs)

    payload = {'vectorizer': vec, 'matrix': X, 'pages': pages}
    with open(INDEX_PATH, 'wb') as f:
        pickle.dump(payload, f)
    return True


def search(query: str, top_k: int = 3) -> Optional[List[Tuple[str,str,float]]]:
    """Search the built index and return list of (url, snippet, score)"""
    if not _ensure_sklearn():
        raise RuntimeError('scikit-learn is required for search. Install with: pip install scikit-learn')
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    if not os.path.exists(INDEX_PATH):
        return None
    with open(INDEX_PATH, 'rb') as f:
        payload = pickle.load(f)
    vec = payload['vectorizer']
    X = payload['matrix']
    pages = payload['pages']

    qv = vec.transform([query])
    sims = cosine_similarity(qv, X).flatten()
    top_idx = sims.argsort()[::-1][:top_k]
    results = []
    for idx in top_idx:
        score = float(sims[idx])
        url = pages[idx].get('url','')
        text = pages[idx].get('text','')
        # create a snippet around first occurrence of a query word
        snippet = text
        results.append((url, snippet[:800].strip(), score))
    return results


if __name__ == '__main__':
    print('Building index...')
    build_index()
    print('Done. Index at', INDEX_PATH)
