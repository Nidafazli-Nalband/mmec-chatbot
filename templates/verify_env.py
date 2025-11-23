"""verify_env.py
Quick script to check for Python and key optional dependencies used by the project.
Run: python verify_env.py
"""
import importlib

modules = [
    ('flask', 'Flask (web server)'),
    ('requests', 'requests (HTTP client, scraping)'),
    ('bs4', 'beautifulsoup4 (HTML parsing)'),
    ('sklearn', 'scikit-learn (TF-IDF index, optional)'),
    ('openai', 'openai (optional AI fallback)'),
    ('google.generativeai', 'google.generativeai (optional Gemini)')
]

missing = []
for mod, desc in modules:
    try:
        importlib.import_module(mod)
    except Exception:
        missing.append((mod, desc))

print('Environment check')
print('=================')
if missing:
    print('Missing the following optional modules:')
    for m,d in missing:
        print(f' - {m}: {d}')
    print('\nInstall with: pip install -r requirements.txt')
else:
    print('All required modules appear installed.')
