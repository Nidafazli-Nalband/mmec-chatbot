Flask server for MMEC Chatbot (prototype)

Files:
- server.py : main Flask app (prototype) - uses local JSON files for storage and optional TF-IDF search
- db_utils.py : a lightweight stub used by admin endpoints
- data/college_info : sample data files (info.md, class_strengths.json)
- fetch_mmec.py : script to scrape mmec.edu.in pages and save them to data/college_info/site_pages.json
- search_index.py : builds a TF-IDF index from scraped pages and performs search
- run_server.ps1 / setup_and_run.ps1 : PowerShell helpers to start and setup the server
- requirements.txt : python dependencies for enhanced features (AI clients, report generation, scraping, search)

Quick start (PowerShell):
1. Open PowerShell and go to the template folder:
   cd 'C:\Users\SONIYA\OneDrive\Desktop\MMMEC AI AGENT\template'

2. Create & activate virtual environment:
   python -m venv .venv
   . .\.venv\Scripts\Activate.ps1

3. Install dependencies:
   python -m pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt

4. Fetch MMEC website (build your local copy of pages):
   python fetch_mmec.py

5. Build the TF-IDF index:
   python -c "import search_index; search_index.build_index()"

6. Run the server:
   python server.py

7. Test endpoints (in PowerShell):
   Invoke-RestMethod -Uri http://localhost:5000/api/status
   Invoke-RestMethod -Uri http://localhost:5000/api/query -Method Post -Body (@{message='student life'; role='Student'} | ConvertTo-Json) -ContentType 'application/json'

Notes & caution:
- Respect robots.txt and crawl politely. This script is a simple crawler for small sites and may not be suitable for large-scale scraping.
- AI providers (OpenAI/Gemini) are optional. The search-based fallback works offline once you've fetched pages and built the index.
- If scikit-learn is not installed, `search_index` will raise an informative error; follow the steps above to install requirements.
