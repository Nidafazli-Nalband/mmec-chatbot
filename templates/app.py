try:
    from flask import Flask, send_from_directory, request, jsonify, send_file
except ImportError as _e:
    # Provide a helpful error at import time so developers know how to fix the environment.
    raise ImportError(
        "Flask is not installed or could not be imported. "
        "Install Flask in your environment with: pip install flask"
    ) from _e
import json
import os
from datetime import datetime
import uuid
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
# Load .env if present to make development easier without committing secrets
try:
    # use dynamic import to avoid static import errors when python-dotenv isn't installed
    import importlib
    dotenv = importlib.import_module('dotenv')
    load_dotenv = getattr(dotenv, 'load_dotenv', None)
    if callable(load_dotenv):
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
except Exception:
    # dotenv is optional; environment variables may be set by the process or OS
    pass

app = Flask(__name__, static_folder='.', static_url_path='')

CHAT_LOG_FILE = 'chat_logs.json'
USERS_FILE = 'users.json'
SETTINGS_FILE = os.path.join('data','settings.json')

# Simple in-memory session store: token -> username
SESSIONS = {}

# SQLite database path
DB_PATH = os.path.join('data', 'users.db')

def init_db():
    """Initialize SQLite database and create users table if not exists."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT,
            password_hash TEXT NOT NULL,
            security_question TEXT,
            answer TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Insert admin if not exists
    cur.execute('SELECT COUNT(*) FROM users WHERE email = ?', ('admin@mmec.edu',))
    if cur.fetchone()[0] == 0:
        admin_hash = generate_password_hash('admin123')
        cur.execute('''
            INSERT INTO users (name, email, mobile, password_hash, security_question, answer)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Admin', 'admin@mmec.edu', '', admin_hash, 'What is the college name?', 'MMEC'))
    conn.commit()
    conn.close()

def _ensure_settings():
    base = os.path.dirname(SETTINGS_FILE)
    if base and not os.path.exists(base):
        os.makedirs(base, exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE,'w',encoding='utf-8') as f:
            json.dump({'allow_external_queries': True}, f)

def read_settings():
    _ensure_settings()
    try:
        with open(SETTINGS_FILE,'r',encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'allow_external_queries': True}

def write_settings(d):
    _ensure_settings()
    with open(SETTINGS_FILE,'w',encoding='utf-8') as f:
        json.dump(d, f, indent=2)

def is_external_allowed():
    # env var overrides file setting
    env = os.getenv('ALLOW_EXTERNAL_QUERIES')
    if env is not None:
        return str(env).lower() in ('1','true','yes')
    s = read_settings()
    return bool(s.get('allow_external_queries', True))

# Load or initialize chat logs
def load_logs():
    if not os.path.exists(CHAT_LOG_FILE):
        with open(CHAT_LOG_FILE, 'w') as f:
            json.dump([], f, indent=2)
    with open(CHAT_LOG_FILE, 'r') as f:
        return json.load(f)

def save_logs(logs):
    with open(CHAT_LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2)

# Load users (simple JSON with plain text passwords for prototype)
def load_users():
    if not os.path.exists(USERS_FILE):
        # default credentials - change in production
        default = {
            "Student": "student123",
            "Faculty": "faculty123",
            "Admin": "admin123"
        }
        with open(USERS_FILE, 'w') as f:
            json.dump(default, f, indent=2)
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

# Serve splash page as front page
@app.route('/')
def index():
    return send_from_directory('.', 'template/splash/splash.html')

# API: Query - receives {message, role}
@app.route('/api/query', methods=['POST'])
def api_query():
    import re
    data = request.get_json() or {}
    message = data.get('message', '')
    role = data.get('role', 'Guest')
    msg_norm = (message or '').strip()
    msg_lower = msg_norm.lower()
    # treat MMEC as full college name for context
    if 'mmec' in msg_lower:
        msg_lower = msg_lower.replace('mmec', 'maratha mandal engineering college')

    # Load offline FAQ from JSON file
    faq_path = os.path.join('data', 'college_info', 'offline_faq.json')
    faq_data = {}
    if os.path.exists(faq_path):
        with open(faq_path, 'r', encoding='utf-8') as f:
            faq_data = json.load(f)

    # Try to match FAQ
    for key, entry in faq_data.items():
        for q in entry.get('questions', []):
            if re.search(re.escape(q.lower()), msg_lower):
                # Add emoji based on category
                emoji_map = {
                    'admission_process': '📝',
                    'branches_courses': '📚',
                    'fee_structure': '💰',
                    'placements': '💼',
                    'contact_information': '📞',
                    'facilities': '🏫',
                    'scholarships': '🎓',
                    'student_activities': '🎉',
                    'results': '📊',
                    'website': '🌐',
                    'about_college': '🏫'
                }
                emoji = emoji_map.get(key, 'ℹ️')
                return jsonify({"answer": f"{emoji} {entry['answer']}", "source": "offline"})

    # College data fallback (existing logic)
    def search_college_files(query_lower):
        try:
            import importlib
            search_index = importlib.import_module('search_index')
            results = search_index.search(message or query_lower, top_k=3)
            if results:
                out = []
                for url, snippet, score in results:
                    out.append(f"Source: {url}\n{snippet}\n")
                return '\n---\n'.join(out)
        except Exception:
            pass
        base = os.path.join('data', 'college_info')
        if not os.path.exists(base):
            return None
        info_path = os.path.join(base, 'info.md')
        try:
            if os.path.exists(info_path):
                with open(info_path, 'r', encoding='utf-8') as f:
                    txt = f.read().lower()
                if query_lower in txt:
                    idx = txt.find(query_lower)
                    start = max(0, idx - 120)
                    snippet = txt[start:start+400].strip()
                    return snippet
        except Exception:
            pass
        for fn in os.listdir(base):
            if fn.endswith('.json'):
                try:
                    with open(os.path.join(base, fn), 'r', encoding='utf-8') as f:
                        j = json.load(f)
                    sj = json.dumps(j).lower()
                    if query_lower in sj:
                        if fn == 'class_strengths.json':
                            response = "Class Strengths at MMEC:\n\n"
                            for dept, data in j.items():
                                if dept == 'faculty_count_other_depts':
                                    continue
                                if isinstance(data, dict):
                                    response += f"{dept}:\n"
                                    for sem, count in data.items():
                                        if sem != 'total':
                                            response += f"  {sem}: {count}\n"
                                    if 'total' in data:
                                        response += f"  Total: {data['total']}\n"
                                elif dept.startswith('CSE_'):
                                    response += f"{dept.replace('CSE_', 'CSE ')}: {data}\n"
                            return response.strip()
                        else:
                            return f"Found relevant data in {fn}. Use the college info panel for details."
                except Exception:
                    continue
        return None

    college_answer = search_college_files(msg_lower)
    if college_answer:
        return jsonify({"answer": college_answer, "source": "college_data"})

    # External query detection
    external_keywords = ['prime minister', 'president', 'india', 'weather', 'news', 'movie', 'stock', 'football', 'cricket', 'recipe']
    if any(k in msg_lower for k in external_keywords):
        ai_answer = call_gemini(message, role)
        prefix = "Note: This is not from MMEC data. "
        return jsonify({"answer": prefix + (ai_answer or 'No external answer available.'), "source": "external"})

    # Default fallback
    return jsonify({"answer": "This chatbot provides information about Maratha Mandal Engineering College (MMEC) only. For other queries please use a general search.", "source": "policy"})
    # API: Total Queries - returns all user queries in a table format
@app.route('/api/total_queries', methods=['GET'])
def api_total_queries():
    logs = load_logs()
    # Return all queries with user email and message
    queries = [
        {
            "name": log.get("user", "Guest"),
            "email": log.get("email", ""),
            "query": log.get("user_msg", ""),
            "answer": log.get("bot_msg", "")
        }
        for log in logs if log.get("user_msg")
    ]
    return jsonify({"ok": True, "queries": queries})

    college_answer = search_college_files(msg_lower)
    if college_answer:
        return jsonify({"answer": college_answer, "source": "college_data"})

    # If we reach here the query is outside our local knowledge. Use AI fallback but keep it college-focused.
    # The policy: the bot is college-only. If the user asks about unrelated topics, respond with a short refusal.
    # Lightweight heuristic: if the query contains words like 'weather','movie','news' treat as outside scope.
    outside_keywords = ['weather', 'movie', 'news', 'stock', 'football', 'cricket', 'recipe']
    if any(k in msg_lower for k in outside_keywords):
        return jsonify({"answer": "This chatbot provides information about Maratha Mandal Engineering College (MMEC) only. For other queries please use a general search.", "source": "policy"})

    # Otherwise call AI fallback (OpenAI preferred)
    ai_answer = call_gemini(message, role)
    # Prefix with disclaimer when AI is used (not official college data)
    prefix = "Note: This answer is not from official MMEC data — "
    # If the ai_answer already contains our '[AI not configured]' style message, return short fallback instead
    if isinstance(ai_answer, str) and ai_answer.startswith('[AI not configured]'):
        # keep it short and actionable
        return jsonify({"answer": "Sorry, AI service is not configured on the server. The chatbot answers college FAQs from local data.", "source": "error"})
    if isinstance(ai_answer, str) and ai_answer.startswith('[AI error]'):
        return jsonify({"answer": "Error contacting AI provider. Try again later or ask a college-specific question.", "source": "error"})
    # Ensure short answer: limit to 400 chars
    if isinstance(ai_answer, str):
        short = ai_answer.strip()
        if len(short) > 400:
            short = short[:390].rsplit('.',1)[0] + '.'
        return jsonify({"answer": prefix + short, "source": "ai"})
    return jsonify({"answer": "Sorry, couldn't generate an answer.", "source": "error"})

@app.route('/api/logs', methods=['GET','POST','DELETE'])
def api_logs():
    # GET: return logs
    if request.method == 'GET':
        logs = load_logs()
        return jsonify({"logs": logs})
    # POST: append a log entry
    if request.method == 'POST':
        data = request.get_json() or {}
        entry = {
            "ts": datetime.utcnow().isoformat() + 'Z',
            "user": data.get('user', 'Guest'),
            "user_msg": data.get('user_msg', ''),
            "bot_msg": data.get('bot_msg', ''),
            "offline": bool(data.get('offline', False))
        }
        logs = load_logs()
        logs.append(entry)
        save_logs(logs)
        return jsonify({"ok": True})
    # DELETE: clear logs
    if request.method == 'DELETE':
        save_logs([])
        return jsonify({"ok": True})


@app.route('/api/login', methods=['POST'])
def api_login():
    """Login endpoint that validates against SQLite users table.
    Expects JSON: { email: "user@example.com", password: "..." }
    Returns: { ok: True, role: "Student"|"Admin", token: "..." } on success or { ok: False, error: 'msg' } on failure
    """
    try:
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return jsonify({"ok": False, "error": "missing credentials"}), 400

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT name, password_hash FROM users WHERE email = ?', (email,))
        row = cur.fetchone()
        conn.close()

        if row and check_password_hash(row[1], password):
            # Determine role: if email is admin@mmec.edu, Admin, else Student
            role = 'Admin' if email == 'admin@mmec.edu' else 'Student'
            token = str(uuid.uuid4())
            SESSIONS[token] = email
            return jsonify({"ok": True, "role": role, "token": token})
        return jsonify({"ok": False, "error": "invalid credentials"}), 401
    except Exception as e:
        print('Login error', e)
        return jsonify({"ok": False, "error": "server error"}), 500


@app.route('/api/register', methods=['POST'])
def api_register():
    """Registration endpoint for students using SQLite DB.
    Expects JSON: { name: 'Full Name', email: 'user@example.com', mobile: '1234567890', password: 'pw', security_question: 'What is your pet name?', answer: 'Fluffy' }
    Stores hashed password in users table.
    """
    try:
        data = request.get_json() or {}
        name = data.get('name')
        email = data.get('email')
        mobile = data.get('mobile')
        password = data.get('password')
        security_question = data.get('security_question')
        answer = data.get('answer')
        if not name or not email or not password:
            return jsonify({"ok": False, "error": "missing required fields"}), 400

        # Hash the password
        password_hash = generate_password_hash(password)

        # Insert into DB
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO users (name, email, mobile, password_hash, security_question, answer)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, email, mobile, password_hash, security_question, answer))
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "user_exists"}), 409
        finally:
            conn.close()

        return jsonify({"ok": True, "email": email})
    except Exception as e:
        print('Register error', e)
        return jsonify({"ok": False, "error": "server error"}), 500



@app.route('/upload', methods=['POST'])
def upload_files():
    """Accept multipart form uploads for logo and student images.
    Expected form fields: file-logo, file-student-1, file-student-2
    Saves files to ./static/ with fixed filenames and returns their public paths.
    """
    upload_dir = os.path.join(os.getcwd(), 'static')
    os.makedirs(upload_dir, exist_ok=True)

    saved = {}
    mapping = [
        ('file-logo', 'logo.jpg'),
        ('file-student-1', 'student_1.jpg'),
        ('file-student-2', 'student_2.jpg'),
    ]
    for field, out_name in mapping:
        f = request.files.get(field)
        if f and getattr(f, 'filename', ''):
            # Save to static folder with consistent filename
            dest = os.path.join(upload_dir, out_name)
            try:
                f.save(dest)
                # return a cache-busting URL so clients update immediately
                saved[field] = f"/static/{out_name}?v={int(datetime.utcnow().timestamp())}"
            except Exception as e:
                print('Failed saving upload', field, e)
    if saved:
        return jsonify({"ok": True, "files": saved})
    return jsonify({"ok": False, "error": "no files uploaded"}), 400

def call_gemini(message, role):
    """
    TODO: Integrate the Gemini API here.
    The intended model is: gemini-2.0-flash (generateContent).
    This function must:
      - Construct the prompt/context (include role or basic system prompt)
      - Send the request to Gemini
      - Return the text response.

    Example notes (developer):
    - Place your Gemini or Google Generative API key in environment variable GEMINI_API_KEY.
    - Using Google Generative API may require client library or service account.
    """
    # Prefer GEMINI_API_KEY, but allow an OpenAI fallback using OPENAI_API_KEY.
    gemini_key = os.getenv('GEMINI_API_KEY', '')
    openai_key = os.getenv('OPENAI_API_KEY', '')

    # Try Gemini (Google Generative) first if key present and library available
    if gemini_key:
        try:
            import importlib
            genai = importlib.import_module('google.generativeai')
            try:
                # some versions/clients expect configure(); others accept api_key
                if hasattr(genai, 'configure'):
                    genai.configure(api_key=gemini_key)
                else:
                    setattr(genai, 'api_key', gemini_key)
            except Exception:
                pass
            # Attempt using GenerativeModel if available
            if hasattr(genai, 'GenerativeModel'):
                try:
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    prompt = (f"You are an assistant for Maratha Mandal Engineering College (MMEC). "
                              f"Answer college-related queries concisely and helpfully. If the user asks unrelated topics, say you only provide MMEC information.\nUser: {message}")
                    resp = model.generate_content(prompt)
                    ans = getattr(resp, 'text', None) or getattr(resp, 'content', None) or str(resp)
                    if isinstance(ans, str):
                        ans = ans.strip()
                        if len(ans) > 800:
                            ans = ans[:790].rsplit('.',1)[0] + '.'
                    return ans
                except Exception as e:
                    print('Gemini model.generate_content error:', e)
            # Fallback: some genai wrappers provide a generate_text helper
            try:
                if hasattr(genai, 'generate_text'):
                    out = genai.generate_text(model='models/text-bison-001', input=f"MMEC assistant: {message}")
                    ans = getattr(out, 'text', None) or str(out)
                    return ans
            except Exception as e:
                print('Gemini generate_text error:', e)
        except Exception as e:
            print('Gemini import/config error:', e)

    # Next: OpenAI fallback (if configured and allowed)
    allow_external = is_external_allowed()
    if openai_key and allow_external:
        try:
            import importlib
            openai = importlib.import_module('openai')
        except Exception as e:
            # OpenAI client library is not installed or cannot be imported
            print('OpenAI import error:', e)
            return "[AI error] OpenAI client library is not installed on the server."
        try:
            openai.api_key = openai_key
            system = "You are an assistant for Maratha Mandal Engineering College (MMEC). Answer college-related queries concisely and helpfully. If the user asks unrelated topics, say you only provide MMEC information."
            resp = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[{'role':'system','content':system},{'role':'user','content':message}],
                max_tokens=300,
                temperature=0.2
            )
            ans = resp.choices[0].message.content.strip()
            if len(ans) > 600:
                ans = ans[:590].rsplit('.',1)[0] + '.'
            return ans
        except Exception as e:
            print('OpenAI call error:', e)
            return "[AI error] Failed to call OpenAI. Check server logs."

    # If nothing worked
    return ("[AI not configured] No usable AI provider configured or external queries are disallowed. "
            "Set OPENAI_API_KEY and ALLOW_EXTERNAL_QUERIES=1 or ensure GEMINI_API_KEY and google.generativeai are installed.")


# Serve college information from data files
@app.route('/api/college_info', methods=['GET'])
def api_college_info():
    info_path = os.path.join('data', 'college_info', 'info.md')
    if os.path.exists(info_path):
        with open(info_path, 'r', encoding='utf-8') as f:
            txt = f.read()
        return jsonify({"ok": True, "text": txt})
    return jsonify({"ok": False, "error": "info not found"}), 404


@app.route('/api/status', methods=['GET'])
def api_status():
    """Return a small status object indicating if AI fallback is configured and allowed.
    Does NOT return any secret keys.
    """
    gemini_key = bool(os.getenv('GEMINI_API_KEY'))
    openai_key = bool(os.getenv('OPENAI_API_KEY'))
    # Check whether gemini client library is installed (so gemini is actually usable)
    gemini_ready = False
    if gemini_key:
        try:
            import importlib
            importlib.import_module('google.generativeai')
            gemini_ready = True
        except Exception:
            gemini_ready = False
    usable = (openai_key and is_external_allowed()) or gemini_ready
    return jsonify({
        "ok": True,
        "ai_provider_available": usable,
        "openai_present": openai_key,
        "gemini_key_present": gemini_key,
        "gemini_ready": gemini_ready,
        "external_allowed": is_external_allowed()
    })


@app.route('/api/class_strengths', methods=['GET'])
def api_class_strengths():
    p = os.path.join('data', 'college_info', 'class_strengths.json')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            return jsonify({"ok": True, "data": json.load(f)})
    return jsonify({"ok": False, "error": "not found"}), 404


# Persist user histories under data/histories/<username>.json
HIST_DIR = os.path.join('data', 'histories')
os.makedirs(HIST_DIR, exist_ok=True)

# Optional SQLite DB (created by migration script)
DB_PATH = os.path.join('data', 'mmec.db')

def db_available():
    return os.path.exists(DB_PATH)

def db_get_history(username, page, size):
    # returns list of items latest-first for compatibility
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    offset = (page-1)*size
    cur.execute('SELECT sender, text, ts FROM histories WHERE username=? ORDER BY id DESC LIMIT ? OFFSET ?', (username, size, offset))
    rows = cur.fetchall()
    conn.close()
    out = []
    for sender, text, ts in rows:
        out.append({'from': sender or 'user', 'text': text or '', 'ts': ts})
    return out

def db_append_history(username, item):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO histories (username, role, sender, text, ts) VALUES (?,?,?,?,?)', (
        username, username, item.get('from','user'), item.get('text',''), item.get('ts', datetime.utcnow().isoformat() + 'Z')
    ))
    conn.commit()
    conn.close()

def db_clear_history(username):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DELETE FROM histories WHERE username=?', (username,))
    conn.commit()
    conn.close()


def history_path(username):
    safe = username.replace('/', '_')
    return os.path.join(HIST_DIR, f'{safe}.json')


@app.route('/api/history', methods=['GET','POST','DELETE'])
def api_history():
    # GET: ?user=Student&page=1&size=20
    if request.method == 'GET':
        user = request.args.get('user', 'guest')
        page = int(request.args.get('page', '1'))
        size = int(request.args.get('size', '20'))
        # If SQLite DB available, use it for histories
        if db_available():
            items = db_get_history(user, page, size)
            # estimate total is unknown here; client uses emptiness to stop
            return jsonify({"ok": True, "history": items, "page": page, "size": size})
        # else fallback to JSON file storage
        p = history_path(user)
        if not os.path.exists(p):
            return jsonify({"ok": True, "history": [], "page": page, "size": size})
        with open(p, 'r', encoding='utf-8') as f:
            hist = json.load(f)
        # return paginated (latest first)
        hist.reverse()
        start = (page-1)*size
        end = start + size
        page_items = hist[start:end]
        return jsonify({"ok": True, "history": page_items, "page": page, "size": size, "total": len(hist)})

    # POST: append history item {user, from, text, ts}
    if request.method == 'POST':
        data = request.get_json() or {}
        user = data.get('user', 'guest')
        item = { 'from': data.get('from','user'), 'text': data.get('text',''), 'ts': data.get('ts') or datetime.utcnow().isoformat() + 'Z' }
        # Use DB if available
        if db_available():
            try:
                db_append_history(user, item)
                return jsonify({"ok": True})
            except Exception as e:
                print('DB append history error', e)
                return jsonify({"ok": False, "error": "db error"}), 500
        # Fallback to JSON file
        p = history_path(user)
        lst = []
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                try:
                    lst = json.load(f)
                except Exception:
                    lst = []
        lst.append(item)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(lst, f, indent=2)
        return jsonify({"ok": True})

    # DELETE: clear user history (expects JSON { user: 'Student' })
    if request.method == 'DELETE':
        data = request.get_json() or {}
        user = data.get('user', 'guest')
        if db_available():
            try:
                db_clear_history(user)
                return jsonify({"ok": True})
            except Exception as e:
                print('DB clear history error', e)
                return jsonify({"ok": False, "error": "db error"}), 500
        p = history_path(user)
        if os.path.exists(p):
            os.remove(p)
        return jsonify({"ok": True})


@app.route('/api/reports/class_strengths', methods=['GET'])
def api_class_strengths_report():
    # Try to generate a simple PDF report if reportlab available; otherwise return JSON
    p = os.path.join('data', 'college_info', 'class_strengths.json')
    if not os.path.exists(p):
        return jsonify({"ok": False, "error": "not found"}), 404
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    try:
        import importlib
        # Dynamically import reportlab modules to avoid static import errors when package is not installed
        rl_pages = importlib.import_module('reportlab.lib.pagesizes')
        rl_canvas_mod = importlib.import_module('reportlab.pdfgen.canvas')
        from io import BytesIO
        letter = rl_pages.letter
        Canvas = rl_canvas_mod.Canvas
        buf = BytesIO()
        c = Canvas(buf, pagesize=letter)
        c.setFont('Helvetica-Bold', 14)
        c.drawString(72, 720, 'Class Strengths Report - MMEC')
        y = 700
        c.setFont('Helvetica', 11)
        for dept, vals in data.items():
            if dept == 'faculty_head' or dept == 'faculty_count_other_depts':
                continue
            c.drawString(72, y, f'{dept}:')
            y -= 16
            for k, v in vals.items():
                c.drawString(92, y, f'{k}: {v}')
                y -= 14
            y -= 8
        c.showPage()
        c.save()
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', download_name='class_strengths.pdf')
    except Exception as e:
        # reportlab not installed or failed, return JSON instead
        return jsonify({"ok": True, "data": data})


@app.route('/api/admin/upload', methods=['POST','GET'])
def api_admin_upload():
    """Authenticated admin upload and list endpoint.
    GET: list files in data/college_info
    POST: multipart form upload with field 'file' and optional 'target' filename
    Requires header: X-Session-Token: <token>
    """
    token = request.headers.get('X-Session-Token') or request.args.get('token')
    user = SESSIONS.get(token)
    if not user or user != 'admin@mmec.edu':
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    base = os.path.join('data', 'college_info')
    os.makedirs(base, exist_ok=True)
    if request.method == 'GET':
        files = []
        for fn in sorted(os.listdir(base)):
            files.append(fn)
        return jsonify({"ok": True, "files": files})

    # POST -> upload
    f = request.files.get('file')
    target = request.form.get('target') or (f.filename if f else None)
    if not f or not target:
        return jsonify({"ok": False, "error": "no file"}), 400
    safe = os.path.basename(target)
    dest = os.path.join(base, safe)
    try:
        f.save(dest)
        return jsonify({"ok": True, "file": safe})
    except Exception as e:
        print('admin upload error', e)
        return jsonify({"ok": False, "error": "failed"}), 500


@app.route('/admin')
def admin_dashboard():
    """Serve admin dashboard - requires login"""
    token = request.args.get('token') or request.cookies.get('session_token')
    user = SESSIONS.get(token) if token else None
    if not user or user != 'admin@mmec.edu':
        return send_from_directory('.', 'index.html')  # Redirect to login
    return send_from_directory('.', 'admin_upload.html')


@app.route('/api/admin/data', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_data():
    """Admin API for managing database data"""
    token = request.headers.get('X-Session-Token') or request.args.get('token')
    user = SESSIONS.get(token)
    if not user or user != 'admin@mmec.edu':
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    import db_utils

    if request.method == 'GET':
        # Get all data from database
        try:
            general_info = db_utils.get_general_info()
            courses = db_utils.get_courses()
            faculty = db_utils.get_faculty()
            fee_structure = db_utils.get_fee_structure()
            timetable = db_utils.get_timetable()

            return jsonify({
                "ok": True,
                "data": {
                    "general_info": general_info,
                    "courses": courses,
                    "faculty": faculty,
                    "fee_structure": fee_structure,
                    "timetable": timetable
                }
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    elif request.method == 'POST':
        # Update data
        data = request.get_json() or {}
        table = data.get('table')
        action = data.get('action', 'update')
        record_data = data.get('data', {})

        try:
            success = False
            if table == 'general_info':
                if action == 'update':
                    key = record_data.get('key')
                    value = record_data.get('value')
                    success = db_utils.update_general_info(key, value)
                elif action == 'delete':
                    key = record_data.get('key')
                    success = db_utils.delete_general_info(key)

            elif table == 'courses':
                if action == 'update':
                    course_code = record_data.get('course_code')
                    course_name = record_data.get('course_name')
                    details = record_data.get('details')
                    success = db_utils.update_course(course_code, course_name, details)
                elif action == 'delete':
                    course_code = record_data.get('course_code')
                    success = db_utils.delete_course(course_code)

            elif table == 'faculty':
                if action == 'update':
                    faculty_id = record_data.get('faculty_id')
                    name = record_data.get('name')
                    department = record_data.get('department')
                    details = record_data.get('details')
                    success = db_utils.update_faculty(faculty_id, name, department, details)
                elif action == 'delete':
                    faculty_id = record_data.get('faculty_id')
                    success = db_utils.delete_faculty(faculty_id)

            elif table == 'fee_structure':
                if action == 'update':
                    course_type = record_data.get('course_type')
                    amount = record_data.get('amount')
                    details = record_data.get('details')
                    success = db_utils.update_fee_structure(course_type, amount, details)
                elif action == 'delete':
                    course_type = record_data.get('course_type')
                    success = db_utils.delete_fee_structure(course_type)

            elif table == 'timetable':
                if action == 'update':
                    day = record_data.get('day')
                    time_slot = record_data.get('time_slot')
                    course_id = record_data.get('course_id')
                    faculty_id = record_data.get('faculty_id')
                    room = record_data.get('room')
                    success = db_utils.update_timetable(day, time_slot, course_id, faculty_id, room)
                elif action == 'delete':
                    day = record_data.get('day')
                    time_slot = record_data.get('time_slot')
                    course_id = record_data.get('course_id')
                    success = db_utils.delete_timetable(day, time_slot, course_id)

            if success:
                return jsonify({"ok": True, "message": f"{action.capitalize()} successful"})
            else:
                return jsonify({"ok": False, "error": f"{action.capitalize()} failed"}), 400

        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/admin/toggle_ai', methods=['POST'])
def api_admin_toggle_ai():
    """Toggle the allow_external_queries setting persisted in data/settings.json.
    Requires header: X-Session-Token: <token> or ?token= in querystring. Only Admin may call.
    Returns: { ok: True, allow_external_queries: bool }
    """
    token = request.headers.get('X-Session-Token') or request.args.get('token')
    user = SESSIONS.get(token)
    if not user or user != 'admin@mmec.edu':
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    # Read, flip, write
    s = read_settings()
    cur = bool(s.get('allow_external_queries', True))
    s['allow_external_queries'] = not cur
    write_settings(s)
    return jsonify({"ok": True, "allow_external_queries": s['allow_external_queries']})

    # Ensure logs file exists
    if not os.path.exists(CHAT_LOG_FILE):
        with open(CHAT_LOG_FILE, 'w') as f:
            json.dump([], f)
    # Ensure users file exists (loaded by load_users)
    _ = load_users()
    app.run(host='0.0.0.0', port=5000, debug=True)
