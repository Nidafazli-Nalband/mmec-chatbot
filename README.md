# MMEC AI Assistant

This repository contains the MMEC AI Assistant (Flask backend + static frontend). The app serves a chat interface for Maratha Mandal Engineering College (MMEC) information and includes an offline FAQ, admin panel, and optional AI fallback integration.

---

**Quick overview**

- Backend: `app.py` (Flask)
- Frontend: Templates under `templates/` (chat UI in `templates/student/chat`)
- Offline FAQ: `data/college_info/offline_faq.json` (new format supported: `{ "faqs": [ ... ] }`)
- Chat logs: `chat_logs.json`
- Users DB: `data/users.db` (SQLite)
- Optional additional DB: `data/mmec.db` (SQLite) used for histories when enabled
- Static assets: `assets/` (images used by UI), `static/` (uploads)

---

## Assets

Included images in `assets/` (excluding `welcome`, `logo`, and `bot` as requested):

- `Admin Dashboard.jpg`
- `Admin Section.jpg`
- `chat.jpg`
- `courses.jpg`
- `login page .jpg`
- `registeration page.jpg`
- `Registered Student.jpg`
- `Student dashboard.jpg`

Note: The bot avatar file expected by the chat UI is `assets/bot.jpeg`. The app will also attempt a fallback to `/static/bot.jpeg` if the asset path isn't available to the browser.

---

## Dependencies

All required Python packages are listed in `requirements.txt`. Primary dependencies:

- Flask
- python-dotenv (optional for env files)
- openai (optional, for OpenAI fallback)
- google-generativeai (optional, for Gemini)
- requests
- beautifulsoup4
- reportlab (optional, PDF report generation)
- scikit-learn, joblib (optional TF-IDF search index)

Install them in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you do not use the AI features, you can omit `openai` and `google-generativeai`.

---

## Environment Variables

The app supports optional AI integrations. Configure these in your environment (or a `.env` file if you prefer):

- `GEMINI_API_KEY` — Google Generative (Gemini) API key (optional)
- `OPENAI_API_KEY` — OpenAI API key (optional fallback)
- `ALLOW_EXTERNAL_QUERIES` — set to `1`, `true`, or `yes` to allow the app to call external AI services

Example (PowerShell):

```powershell
$env:OPENAI_API_KEY = 'sk-...'
$env:ALLOW_EXTERNAL_QUERIES = '1'
python app.py
```

---

## Running the App

From the project root:

```powershell
# Windows PowerShell
python app.py
# or use the provided script if available
# .\run_server.ps1
```

The Flask server runs on `http://0.0.0.0:5502` by default (see `app.py`). Open `http://127.0.0.1:5502/student/chat` for the chat UI.

On first run the app creates necessary DBs and files:

- `data/users.db` — main users table and login records
- `data/mmec.db` — additional histories DB (optional)
- `chat_logs.json` — chat logs file

A default admin user is inserted if missing. The default admin email is set in `app.py` (`ADMIN_EMAILS`) and the default password inserted during initialization is `Nida@123` for the default admin user.

---

## Notable Endpoints

- `POST /api/query` — main chat query endpoint (expects JSON `{ message, role }`)
- `GET/POST/DELETE /api/logs` — read/append/clear chat logs
- `GET /api/offline_faq` — returns raw offline FAQ JSON
- `GET /api/college_info` — returns `data/college_info/info.md` if present
- Admin APIs (require admin session token `X-Session-Token`):
  - `POST /api/admin/reply` — save admin reply to a log entry
  - `POST /api/admin/delete_log` — delete a log entry
  - `POST /api/admin/delete_student` — permanently delete student records and related logs/histories

Notes on deletion:
- `/api/admin/delete_student` permanently removes the user's row(s) from `users.db`, their `logins` and `user_actions`, `histories` (DB and per-user JSON files under `data/histories/`), and purges matching entries from `chat_logs.json`.

---

## Offline FAQ Format

The server supports both the legacy and the new format. Preferred new format (example):

```json
{
  "faqs": [
    {
      "keyword": "about college",
      "keywords": ["about","college","mmec"],
      "answer": "<b>Maratha Mandal Engineering College (MMEC)</b> ..."
    }
  ]
}
```

If you keep the old structure (top-level keys each containing a `questions` list and an `answer`), the server will still normalize and search it.

---

## Log storage behavior

Saved chat logs are written to `chat_logs.json`. To keep stored logs clean, the server strips AI-disclaimer prefixes and generic "found" messages before saving. This prevents storing lines such as "Note: This answer is not from official MMEC data" or "Found relevant data in ..." in the saved logs.

---

## Static Files and Bot Avatar

Place your bot avatar at `assets/bot.jpeg` (or in `static/` as `bot.jpeg`) so the chat header avatar loads correctly.

If you want the bot avatar shown next to every bot message, I can update `templates/student/chat/chat.js` to include it when rendering messages.

---

## Common Tasks

- Restart server after edits:
```powershell
# stop process (Ctrl+C) then
python app.py
```

- Reset chat logs:
```powershell
Remove-Item .\chat_logs.json; python app.py
```

- Inspect the SQLite DB:
```powershell
# Windows: use sqlite3 if available
sqlite3 data\users.db
.sqlite> .tables
.sqlite> select * from users limit 5;
```

---

## Troubleshooting

- If the chat returns AI fallback errors, ensure `OPENAI_API_KEY` or `GEMINI_API_KEY` are set and `ALLOW_EXTERNAL_QUERIES=1` if you want to allow external AI.
- If images don't load from `/assets`, try copying them to `/static/` and refresh the page to bypass OneDrive/permission issues.

---

If you want, I can also:

- Add bot avatars next to each bot message in the chat history UI.
- Implement a soft-delete mode for students instead of permanent removal.
- Run a quick local test (start server and hit a sample query) and show the result.

---

Happy to continue — tell me which of the optional follow-ups you'd like me to do next.
