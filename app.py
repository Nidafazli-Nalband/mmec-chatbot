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


app = Flask(__name__, static_folder='templates', static_url_path='')

# Serve assets directory (bot avatar and other images)
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(os.getcwd(), 'assets'), filename)

CHAT_LOG_FILE = 'chat_logs.json'
USERS_FILE = 'users.json'
SETTINGS_FILE = os.path.join('data','settings.json')

# Centralized admin list (single admin as requested)
ADMIN_EMAILS = ['nidafazlinalband@gmail.com']

# Simple in-memory session store: token -> username
SESSIONS = {}

def get_token_from_request():
    """Extract token from X-Session-Token header or Authorization: Bearer <token> or ?token= query param."""
    auth = request.headers.get('X-Session-Token') or request.headers.get('Authorization') or request.args.get('token')
    if not auth:
        return None
    # If Authorization: Bearer <token>
    try:
        if isinstance(auth, str) and auth.lower().startswith('bearer '):
            return auth.split(None, 1)[1]
    except Exception:
        pass
    return auth

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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT,
            marks TEXT,
            notes TEXT,
            chat_permission INTEGER DEFAULT 1
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT NOT NULL,
            login_time TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # Add new columns if not exist
    try:
        cur.execute('ALTER TABLE users ADD COLUMN marks TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute('ALTER TABLE users ADD COLUMN notes TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute('ALTER TABLE users ADD COLUMN chat_permission INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass
    # Insert configured admins if not exists (use ADMIN_EMAILS and create one admin user)
    admin_default = ('Nida Fazli', ADMIN_EMAILS[0], '', 'Nida@123')
    name, email, mobile, pw = admin_default
    cur.execute('SELECT COUNT(*) FROM users WHERE email = ?', (email,))
    if cur.fetchone()[0] == 0:
        cur.execute('''
            INSERT INTO users (name, email, mobile, password_hash, security_question, answer)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, email, mobile, generate_password_hash(pw), '', ''))
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


def load_offline_faq_normalized():
    """Load offline_faq.json and normalize to a list of faq entries.
    Supports both old format (top-level keys with 'questions' + 'answer')
    and new format { "faqs": [ { keyword, keywords, answer }, ... ] }.
    Returns list of dicts with keys: 'keywords' (list of strings) and 'answer'.
    """
    p = os.path.join('data', 'college_info', 'offline_faq.json')
    if not os.path.exists(p):
        return []
    try:
        with open(p, 'r', encoding='utf-8') as f:
            j = json.load(f)
    except Exception:
        return []
    out = []
    # New style: {'faqs': [ ... ]}
    if isinstance(j, dict) and 'faqs' in j and isinstance(j['faqs'], list):
        for item in j['faqs']:
            kws = []
            if isinstance(item.get('keywords'), list):
                kws = [str(x).lower() for x in item.get('keywords')]
            # also include the main 'keyword' if present
            if item.get('keyword'):
                kws.append(str(item.get('keyword')).lower())
            out.append({'keywords': kws, 'answer': item.get('answer')})
        return out
    # Old style: top-level keys each with 'questions'
    if isinstance(j, dict):
        for k, v in j.items():
            if isinstance(v, dict):
                kws = []
                if isinstance(v.get('questions'), list):
                    kws = [str(x).lower() for x in v.get('questions')]
                # include the key name as a keyword too
                kws.append(str(k).lower())
                out.append({'keywords': kws, 'answer': v.get('answer')})
    return out

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
    return send_from_directory('.', 'templates/splash/splash.html')

# API: Query - receives {message, role}
@app.route('/api/query', methods=['POST'])
def api_query():
    data = request.get_json() or {}
    message = data.get('message', '')
    role = data.get('role', 'Guest')
    # Normalize message and treat MMEC specially
    msg_norm = (message or '').strip()
    msg_lower = msg_norm.lower()
    # treat MMEC as full college name for context
    if 'mmec' in msg_lower:
        msg_lower = msg_lower.replace('mmec', 'maratha mandal engineering college')

    # Check admin-provided FAQs first (persisted answers inserted by admin)
    def search_admin_faqs(query_lower):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            # simple containment search in question or keywords
            cur.execute("SELECT question,answer,keywords FROM admin_faqs ORDER BY id DESC")
            rows = cur.fetchall()
            conn.close()
            for q,a,k in rows:
                if not q:
                    continue
                ql = q.lower()
                if query_lower in ql or ql in query_lower:
                    return a
                if k:
                    if any(tok.strip() and tok.lower() in query_lower for tok in str(k).split(',')):
                        return a
        except Exception:
            pass
        return None

    # Check offline FAQ next (supports both legacy and new formats)
    faqs = load_offline_faq_normalized()
    def sanitize_bot_msg(msg):
        if not isinstance(msg, str):
            return msg
        skip_phrases = [
            'Not from MMEC data or not found in college files.',
            'Note: This answer is not from official MMEC data',
            'Found relevant data in',
            'not found in',
            'This chatbot provides information about Maratha Mandal Engineering College',
            'Sorry, AI service is not configured on the server',
            'Error contacting AI provider',
            'Found relevant data in offline_faq.json'
        ]
        # Remove each phrase from every line
        lines = msg.splitlines()
        cleaned = []
        for line in lines:
            for p in skip_phrases:
                line = line.replace(p, '')
            line = line.replace('Note:', '').replace('Note -', '').strip()
            line = line.lstrip(':-–— \n').strip()
            if line:  # Only keep non-empty lines
                cleaned.append(line)
        return '\n'.join(cleaned)

    # admin faq check
    admin_ans = search_admin_faqs(msg_lower)
    if admin_ans:
        return jsonify({"answer": admin_ans, "source": "admin_faq"})

    for item in faqs:
        for q in item.get('keywords', []):
            try:
                if q and (q in msg_lower or msg_lower in q):
                    answer = sanitize_bot_msg(item.get('answer'))
                    return jsonify({"answer": answer, "source": "offline"})
            except Exception:
                continue

    # Prefer using the optional TF-IDF search index if available (search_index.py)
    def search_college_files(query_lower):
        try:
            import importlib
            search_index = importlib.import_module('search_index')
            # search_index expects the original query (not lowercased) for better results
            results = search_index.search(message or query_lower, top_k=3)
            if results:
                # format a helpful answer from top result(s)
                out = []
                for url, snippet, score in results:
                    out.append(f"Source: {url}\n{snippet}\n")
                return '\n---\n'.join(out)
        except Exception:
            # fallback to file-based search below
            pass

        base = os.path.join('data', 'college_info')
        if not os.path.exists(base):
            return None
        # check info.md for phrase matches
        info_path = os.path.join(base, 'info.md')
        try:
            if os.path.exists(info_path):
                with open(info_path, 'r', encoding='utf-8') as f:
                    txt = f.read().lower()
                if query_lower in txt:
                    # return a short extract: first 400 chars around first occurrence
                    idx = txt.find(query_lower)
                    start = max(0, idx - 120)
                    snippet = txt[start:start+400].strip()
                    return snippet
        except Exception:
            pass
        # check json files for keys or values
        for fn in os.listdir(base):
            if fn.endswith('.json'):
                try:
                    with open(os.path.join(base, fn), 'r', encoding='utf-8') as f:
                        j = json.load(f)
                    sj = json.dumps(j).lower()
                    if query_lower in sj:
                        # return the actual data instead of a generic message
                        if fn == 'class_strengths.json':
                            # Format the class strengths data nicely
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
                        elif fn == 'offline_faq.json':
                            # For offline_faq.json, support both old and new formats
                            try:
                                # Normalize and search
                                norm = []
                                if isinstance(j, dict) and 'faqs' in j and isinstance(j['faqs'], list):
                                    for it in j['faqs']:
                                        kws = []
                                        if isinstance(it.get('keywords'), list):
                                            kws = [str(x).lower() for x in it.get('keywords')]
                                        if it.get('keyword'):
                                            kws.append(str(it.get('keyword')).lower())
                                        norm.append({'keywords': kws, 'answer': it.get('answer')})
                                elif isinstance(j, dict):
                                    for cat, data in j.items():
                                        kws = []
                                        if isinstance(data.get('questions'), list):
                                            kws = [str(x).lower() for x in data.get('questions')]
                                        kws.append(str(cat).lower())
                                        norm.append({'keywords': kws, 'answer': data.get('answer')})
                                for it in norm:
                                    for q in it.get('keywords', []):
                                        if q and (q in msg_lower or msg_lower in q):
                                            return it.get('answer', f"Found relevant data in {fn}. Use the college info panel for details.")
                            except Exception:
                                pass
                            # If no match, return generic
                            return f"Found relevant data in {fn}. Use the college info panel for details."
                        else:
                            # For other files, return a summary
                            return f"Found relevant data in {fn}. Use the college info panel for details."
                except Exception:
                    continue
        return None

    college_answer = search_college_files(msg_lower)
    if college_answer:
        answer = sanitize_bot_msg(college_answer)
        return jsonify({"answer": answer, "source": "college_data"})

    # If we reach here the query is outside our local knowledge. Use AI fallback but keep it college-focused.
    # The policy: the bot is college-only. If the user asks about unrelated topics, respond with a short refusal.
    # Lightweight heuristic: if the query contains words like 'weather','movie','news' treat as outside scope.
    outside_keywords = ['weather', 'movie', 'news', 'stock', 'football', 'cricket', 'recipe']
    if any(k in msg_lower for k in outside_keywords):
        answer = sanitize_bot_msg("This chatbot provides information about Maratha Mandal Engineering College (MMEC) only. For other queries please use a general search.")
        return jsonify({"answer": answer, "source": "policy"})

    # Try to scrape relevant content from www.mmec.edu.in
    scraped_content = scrape_mmec_website(msg_lower)
    if scraped_content:
        # Use AI to generate answer based on scraped content
        ai_answer = call_gemini(message, role, scraped_content)
    else:
        # Otherwise call AI fallback (OpenAI preferred)
        ai_answer = call_gemini(message, role)
    # Prefix with disclaimer when AI is used (not official college data)
    prefix = "Note: This answer is not from official MMEC data — "
    # If the ai_answer already contains our '[AI not configured]' style message, return short fallback instead
    if isinstance(ai_answer, str) and ai_answer.startswith('[AI not configured]'):
        # record as unanswered for admin review and return short message
        try:
            record_unanswered(message)
        except Exception:
            pass
        answer = sanitize_bot_msg("Sorry, AI service is not configured on the server. The chatbot answers college FAQs from local data.")
        return jsonify({"answer": answer, "source": "error"})
    if isinstance(ai_answer, str) and ai_answer.startswith('[AI error]'):
        try:
            record_unanswered(message)
        except Exception:
            pass
        answer = sanitize_bot_msg("Error contacting AI provider. Try again later or ask a college-specific question.")
        return jsonify({"answer": answer, "source": "error"})
    # Ensure short answer: limit to 400 chars
    if isinstance(ai_answer, str):
        short = ai_answer.strip()
        if len(short) > 400:
            short = short[:390].rsplit('.',1)[0] + '.'
        answer = sanitize_bot_msg(prefix + short)
        return jsonify({"answer": answer, "source": "ai"})
    try:
        record_unanswered(message)
    except Exception:
        pass
    answer = sanitize_bot_msg("Sorry, couldn't generate an answer.")
    return jsonify({"answer": answer, "source": "error"})

@app.route('/api/logs', methods=['GET','POST','DELETE'])
def api_logs():
    # GET: return logs
    if request.method == 'GET':
        logs = load_logs()
        return jsonify({"logs": logs})
    # POST: append a log entry
    if request.method == 'POST':
        data = request.get_json() or {}
        bot_msg = data.get('bot_msg', '')
        # If bot_msg contains the unwanted line, skip saving this entry entirely
        skip_phrases = [
            'Note: This answer is not from official MMEC data',
            'Found relevant data in',
            'not found in',
            'This chatbot provides information about Maratha Mandal Engineering College',
            'Sorry, AI service is not configured on the server',
            'Error contacting AI provider',
            'Found relevant data in offline_faq.json'
        ]
        if any(p.lower() in bot_msg.lower() for p in skip_phrases):
            # Do not save this log entry at all
            return jsonify({"ok": True, "skipped": True})

        entry = {
            "id": str(uuid.uuid4()),
            "ts": datetime.utcnow().isoformat() + 'Z',
            "user": data.get('user', 'Guest'),
            "user_msg": data.get('user_msg', ''),
            "bot_msg": bot_msg,
            "offline": bool(data.get('offline', False))
        }
        # Sanitize bot message before saving: strip common AI disclaimers or generic 'found' messages
        try:
            bm = (entry.get('bot_msg') or '')
            if isinstance(bm, str):
                b = bm
                for p in skip_phrases:
                    b = b.replace(p, '')
                b = b.replace('Note:', '').replace('Note -', '').strip()
                b = b.lstrip(':-–— \n').strip()
                if len(b) < 5:
                    b = ''
                entry['bot_msg'] = b
        except Exception:
            pass

        logs = load_logs()
        logs.append(entry)
        save_logs(logs)
        return jsonify({"ok": True})
    # DELETE: clear logs
    if request.method == 'DELETE':
        save_logs([])
        return jsonify({"ok": True})


@app.route('/api/admin/reply', methods=['POST'])
def api_admin_reply():
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json() or {}
    entry_id = data.get('id') or data.get('ts')
    reply = data.get('reply')
    if not entry_id or not reply:
        return jsonify({"ok": False, "error": "missing parameters"}), 400
    logs = load_logs()
    found = False
    for entry in logs:
        if entry.get('id') == entry_id or entry.get('ts') == entry_id:
            entry['bot_msg'] = reply
            entry['answered_by'] = user
            entry['answered_at'] = datetime.utcnow().isoformat() + 'Z'
            found = True
            break
    if not found:
        return jsonify({"ok": False, "error": "not found"}), 404
    save_logs(logs)
    return jsonify({"ok": True})


@app.route('/api/admin/delete_log', methods=['POST'])
def api_admin_delete_log():
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json() or {}
    entry_id = data.get('id') or data.get('ts')
    if not entry_id:
        return jsonify({"ok": False, "error": "missing id"}), 400
    logs = load_logs()
    new_logs = [l for l in logs if not (l.get('id') == entry_id or l.get('ts') == entry_id)]
    if len(new_logs) == len(logs):
        return jsonify({"ok": False, "error": "not found"}), 404
    save_logs(new_logs)
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
            # Determine role: Admin if in ADMIN_EMAILS else Student
            role = 'Admin' if email in ADMIN_EMAILS else 'Student'
            name = row[0]
            token = str(uuid.uuid4())
            SESSIONS[token] = email
            # Log the login
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('SELECT id FROM users WHERE email = ?', (email,))
            user_id = cur.fetchone()[0]
            ip_address = request.remote_addr or 'unknown'
            cur.execute('INSERT INTO logins (user_id, email, ip_address) VALUES (?, ?, ?)', (user_id, email, ip_address))
            conn.commit()
            conn.close()
            return jsonify({"ok": True, "role": role, "token": token, "name": name})
        return jsonify({"ok": False, "error": "invalid credentials"}), 401
    except Exception as e:
        print('Login error', e)
        return jsonify({"ok": False, "error": "server error"}), 500


@app.route('/home')
def home_page():
    return send_from_directory('.', 'templates/home/home.html')

@app.route('/admissions')
def admissions_page():
    return send_from_directory('.', 'templates/admissions/admissions.html')

@app.route('/courses')
def courses_page():
    return send_from_directory('.', 'templates/courses/courses.html')

@app.route('/facilities')
def facilities_page():
    return send_from_directory('.', 'templates/facilities/facilities.html')

@app.route('/placements')
def placements_page():
    return send_from_directory('.', 'templates/placements/placements.html')

@app.route('/events')
def events_page():
    return send_from_directory('.', 'templates/events/events.html')

@app.route('/about')
def about_page():
    return send_from_directory('.', 'templates/about/about.html')

@app.route('/contact')
def contact_page():
    return send_from_directory('.', 'templates/contact/contact.html')

@app.route('/login')
def login_page():
    return send_from_directory('.', 'templates/login/login.html')

@app.route('/student/dashboard')
def student_dashboard():
    return send_from_directory('.', 'templates/student/dashboard/dashboard.html')

@app.route('/student/chat')
def student_chat():
    return send_from_directory('.', 'templates/student/chat/chat.html')


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

def scrape_mmec_website(query_lower):
    """Scrape relevant content from www.mmec.edu.in based on query keywords."""
    try:
        import importlib
        requests = importlib.import_module('requests')
        bs4 = importlib.import_module('bs4')
        BeautifulSoup = bs4.BeautifulSoup
    except ImportError:
        return None  # Libraries not installed

    base_url = 'https://www.mmec.edu.in'
    # Define relevant pages based on keywords
    pages = {
        'admission': '/admission',
        'fee': '/fee-structure',
        'course': '/courses',
        'facility': '/facilities',
        'placement': '/placements',
        'about': '/about',
        'contact': '/contact'
    }

    relevant_pages = []
    for keyword, path in pages.items():
        if keyword in query_lower:
            relevant_pages.append(base_url + path)

    if not relevant_pages:
        # Default to home page if no specific match
        relevant_pages = [base_url]

    scraped_text = ""
    for url in relevant_pages[:3]:  # Limit to 3 pages to avoid too much data
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Extract text from main content areas, remove scripts/styles
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator=' ', strip=True)
            scraped_text += f"From {url}:\n{text[:2000]}\n\n"  # Limit text per page
        except Exception as e:
            print(f"Scraping error for {url}: {e}")
            continue

    return scraped_text.strip() if scraped_text else None

def call_gemini(message, role, scraped_content=None):
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
                    context = f"Additional context from MMEC website:\n{scraped_content}\n\n" if scraped_content else ""
                    prompt = (f"You are an assistant for Maratha Mandal Engineering College (MMEC). "
                              f"Answer college-related queries concisely and helpfully. If the user asks unrelated topics, say you only provide MMEC information.\n{context}User: {message}")
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

def record_unanswered(question):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # avoid duplicate exact questions
        cur.execute('SELECT id FROM unanswered_queries WHERE question = ?', (question,))
        if cur.fetchone():
            conn.close()
            return
        cur.execute('INSERT INTO unanswered_queries (question) VALUES (?)', (question,))
        conn.commit()
        conn.close()
    except Exception:
        pass


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

@app.route('/api/offline_faq', methods=['GET'])
def api_offline_faq():
    p = os.path.join('data', 'college_info', 'offline_faq.json')
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            return jsonify({"ok": True, "faq": json.load(f)})
    return jsonify({"ok": False, "error": "not found"}), 404


# Persist user histories under data/histories/<username>.json
HIST_DIR = os.path.join('data', 'histories')
os.makedirs(HIST_DIR, exist_ok=True)

# Optional SQLite DB (created by migration script)
DB_PATH = os.path.join('data', 'mmec.db')

def db_available():
    return os.path.exists(DB_PATH)


def init_mmec_db():
    """Ensure mmec.db exists and required tables are present for histories and chat."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # histories table used by the application
    cur.execute('''
        CREATE TABLE IF NOT EXISTS histories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            sender TEXT,
            text TEXT,
            ts TEXT
        )
    ''')
    # legacy / alternate tables requested by schema
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student'
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            reply TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS unanswered_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Attempt to add columns for answer tracking if missing
    try:
        cur.execute('ALTER TABLE unanswered_queries ADD COLUMN answer TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute('ALTER TABLE unanswered_queries ADD COLUMN answered INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute('ALTER TABLE unanswered_queries ADD COLUMN answered_at TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute('ALTER TABLE unanswered_queries ADD COLUMN answered_by TEXT')
    except sqlite3.OperationalError:
        pass

    # Admin-provided FAQ table: stores admin-inserted Q->A pairs for immediate reuse
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admin_faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            keywords TEXT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

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
        text = data.get('text','')
        # If the text contains the unwanted line, skip saving this history item
        skip_phrases = [
            'Not from MMEC data or not found in college files.',
            'Note: This answer is not from official MMEC data',
            'Found relevant data in',
            'not found in',
            'This chatbot provides information about Maratha Mandal Engineering College',
            'Sorry, AI service is not configured on the server',
            'Error contacting AI provider',
            'Found relevant data in offline_faq.json'
        ]
        if any(p.lower() in text.lower() for p in skip_phrases):
            return jsonify({"ok": True, "skipped": True})

        item = { 'from': data.get('from','user'), 'text': text, 'ts': data.get('ts') or datetime.utcnow().isoformat() + 'Z' }
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
        ts = data.get('ts')
        # If ts provided, delete single history item matching timestamp
        if ts:
            if db_available():
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    cur.execute('DELETE FROM histories WHERE username=? AND ts=?', (user, ts))
                    conn.commit()
                    conn.close()
                    return jsonify({"ok": True})
                except Exception as e:
                    print('DB delete history item error', e)
                    return jsonify({"ok": False, "error": "db error"}), 500
            p = history_path(user)
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        lst = json.load(f)
                except Exception:
                    lst = []
                new = [it for it in lst if it.get('ts') != ts]
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(new, f, indent=2)
            return jsonify({"ok": True})

        # Otherwise clear all history for user
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
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
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
    token = get_token_from_request() or request.cookies.get('session_token')
    user = SESSIONS.get(token) if token else None

    if not user or user not in ADMIN_EMAILS:
        return send_from_directory('.', 'templates/login/login.html')  # Redirect to login
    return send_from_directory('.', 'templates/admin/admin.html')


@app.route('/api/admin/data', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_data():
    """Admin API for managing database data"""
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
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
            # Support 'read' action to get a single table's data (used by admin UI)
            if action == 'read':
                if table == 'general_info':
                    return jsonify({"ok": True, "data": db_utils.get_general_info()})
                elif table == 'courses':
                    return jsonify({"ok": True, "data": db_utils.get_courses()})
                elif table == 'faculty':
                    return jsonify({"ok": True, "data": db_utils.get_faculty()})
                elif table == 'fee_structure':
                    return jsonify({"ok": True, "data": db_utils.get_fee_structure()})
                elif table == 'timetable':
                    return jsonify({"ok": True, "data": db_utils.get_timetable()})
                else:
                    return jsonify({"ok": False, "error": "unknown table"}), 400

            # Allow 'insert' to behave like 'update' (db_utils uses INSERT OR REPLACE)
            if action == 'insert':
                action = 'update'

            if table == 'general_info':
                if action == 'update':
                    key = record_data.get('key') or data.get('key')
                    value = record_data.get('value') or data.get('value')
                    if not key:
                        return jsonify({"ok": False, "error": "missing key"}), 400
                    success = db_utils.update_general_info(key, value)
                elif action == 'delete':
                    key = record_data.get('key') or data.get('key')
                    success = db_utils.delete_general_info(key)
                # If updated successfully, also store in admin_faqs for direct chat responses
                if success:
                    try:
                        conn2 = sqlite3.connect(DB_PATH)
                        cur2 = conn2.cursor()
                        cur2.execute('INSERT INTO admin_faqs (question, answer, keywords, ts) VALUES (?, ?, ?, ?)', (key, str(value), '', datetime.utcnow().isoformat() + 'Z'))
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass

            elif table == 'courses':
                if action == 'update':
                    course_code = record_data.get('course_code') or data.get('course_code')
                    course_name = record_data.get('course_name') or data.get('course_name')
                    details = record_data.get('details') or data.get('details')
                    if not course_code:
                        return jsonify({"ok": False, "error": "missing course_code"}), 400
                    success = db_utils.update_course(course_code, course_name, details)
                elif action == 'delete':
                    course_code = record_data.get('course_code')
                    success = db_utils.delete_course(course_code)
                # Persist to admin_faqs so students receive this updated course info immediately
                if success and course_code:
                    try:
                        conn2 = sqlite3.connect(DB_PATH)
                        cur2 = conn2.cursor()
                        ans = f"{course_name or ''}\n\n{details or ''}".strip()
                        cur2.execute('INSERT INTO admin_faqs (question, answer, keywords, ts) VALUES (?, ?, ?, ?)', (course_code, ans, course_name or '', datetime.utcnow().isoformat() + 'Z'))
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass

            elif table == 'faculty':
                if action == 'update':
                    faculty_id = record_data.get('faculty_id') or data.get('faculty_id')
                    name = record_data.get('name') or data.get('name')
                    department = record_data.get('department') or data.get('department')
                    details = record_data.get('details') or data.get('details')
                    if not faculty_id:
                        return jsonify({"ok": False, "error": "missing faculty_id"}), 400
                    success = db_utils.update_faculty(faculty_id, name, department, details)
                elif action == 'delete':
                    faculty_id = record_data.get('faculty_id')
                    success = db_utils.delete_faculty(faculty_id)
                if success and faculty_id:
                    try:
                        conn2 = sqlite3.connect(DB_PATH)
                        cur2 = conn2.cursor()
                        ans = f"{name or ''} ({department or ''})\n\n{details or ''}".strip()
                        cur2.execute('INSERT INTO admin_faqs (question, answer, keywords, ts) VALUES (?, ?, ?, ?)', (faculty_id, ans, name or '', datetime.utcnow().isoformat() + 'Z'))
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass

            elif table == 'fee_structure':
                if action == 'update':
                    course_type = record_data.get('course_type') or data.get('course_type')
                    amount = record_data.get('amount') or data.get('amount')
                    details = record_data.get('details') or data.get('details')
                    if not course_type:
                        return jsonify({"ok": False, "error": "missing course_type"}), 400
                    success = db_utils.update_fee_structure(course_type, amount, details)
                elif action == 'delete':
                    course_type = record_data.get('course_type')
                    success = db_utils.delete_fee_structure(course_type)
                if success and course_type:
                    try:
                        conn2 = sqlite3.connect(DB_PATH)
                        cur2 = conn2.cursor()
                        ans = f"Fees for {course_type}: {amount or ''}\n\n{details or ''}".strip()
                        cur2.execute('INSERT INTO admin_faqs (question, answer, keywords, ts) VALUES (?, ?, ?, ?)', (course_type, ans, '', datetime.utcnow().isoformat() + 'Z'))
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass

            elif table == 'timetable':
                if action == 'update':
                    day = record_data.get('day') or data.get('day')
                    time_slot = record_data.get('time_slot') or data.get('time_slot')
                    course_id = record_data.get('course_id') or data.get('course_id')
                    faculty_id = record_data.get('faculty_id') or data.get('faculty_id')
                    room = record_data.get('room') or data.get('room')
                    if not day or not time_slot or not course_id:
                        return jsonify({"ok": False, "error": "missing timetable keys"}), 400
                    success = db_utils.update_timetable(day, time_slot, course_id, faculty_id, room)
                elif action == 'delete':
                    day = record_data.get('day')
                    time_slot = record_data.get('time_slot')
                    course_id = record_data.get('course_id')
                    success = db_utils.delete_timetable(day, time_slot, course_id)
                if success and day and time_slot and course_id:
                    try:
                        conn2 = sqlite3.connect(DB_PATH)
                        cur2 = conn2.cursor()
                        ans = f"Timetable: {day} {time_slot} - {course_id} in {room or ''} (Faculty: {faculty_id or ''})"
                        key = f"{course_id} {day} {time_slot}"
                        cur2.execute('INSERT INTO admin_faqs (question, answer, keywords, ts) VALUES (?, ?, ?, ?)', (key, ans, course_id or '', datetime.utcnow().isoformat() + 'Z'))
                        conn2.commit()
                        conn2.close()
                    except Exception:
                        pass

            if success:
                return jsonify({"ok": True, "message": f"{action.capitalize()} successful"})
            else:
                return jsonify({"ok": False, "error": f"{action.capitalize()} failed"}), 400

        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


    @app.route('/api/admin/delete_student', methods=['POST'])
    def api_admin_delete_student():
        """Delete student record and related data permanently.
        Request JSON: { email: 'user@example.com', block: true }
        Requires admin session token.
        """
        token = get_token_from_request()
        user = SESSIONS.get(token)
        if not user or user not in ADMIN_EMAILS:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        data = request.get_json() or {}
        email = data.get('email')
        if not email:
            return jsonify({"ok": False, "error": "email required"}), 400
        try:
            # Remove from SQLite users table
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('DELETE FROM users WHERE email = ?', (email,))
            cur.execute('DELETE FROM logins WHERE email = ?', (email,))
            cur.execute('DELETE FROM user_actions WHERE email = ?', (email,))
            conn.commit()
            conn.close()

            # Remove from mmec.db histories if present
            try:
                if os.path.exists(DB_PATH):
                    conn2 = sqlite3.connect(DB_PATH)
                    cur2 = conn2.cursor()
                    cur2.execute('DELETE FROM histories WHERE username = ? OR role = ?', (email, email))
                    conn2.commit()
                    conn2.close()
            except Exception:
                pass

            # Remove any history JSON file
            try:
                hist_file = history_path(email)
                if os.path.exists(hist_file):
                    os.remove(hist_file)
            except Exception:
                pass

            # Remove chat logs entries for this user
            try:
                logs = load_logs()
                new_logs = [l for l in logs if l.get('user') != email and l.get('user') != email.split('@')[0]]
                save_logs(new_logs)
            except Exception:
                pass

            # Remove from users.json fallback (if present)
            try:
                if os.path.exists(USERS_FILE):
                    with open(USERS_FILE, 'r', encoding='utf-8') as f:
                        u = json.load(f)
                    changed = False
                    if isinstance(u, dict) and email in u:
                        u.pop(email, None)
                        changed = True
                    if changed:
                        with open(USERS_FILE, 'w', encoding='utf-8') as f:
                            json.dump(u, f, indent=2)
            except Exception:
                pass

            return jsonify({"ok": True})
        except Exception as e:
            print('admin delete student error', e)
            return jsonify({"ok": False, "error": "server error"}), 500


@app.route('/api/admin/toggle_ai', methods=['POST'])
def api_admin_toggle_ai():
    """Toggle the allow_external_queries setting persisted in data/settings.json.
    Requires header: X-Session-Token: <token> or ?token= in querystring. Only Admin may call.
    Returns: { ok: True, allow_external_queries: bool }
    """
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    # Read, flip, write
    s = read_settings()
    cur = bool(s.get('allow_external_queries', True))
    s['allow_external_queries'] = not cur
    write_settings(s)
    return jsonify({"ok": True, "allow_external_queries": s['allow_external_queries']})

@app.route('/api/admin/students', methods=['GET'])
def api_admin_students():
    """Get list of all registered students."""
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Return created_at as registration date when available
    cur.execute('SELECT name, email, marks, notes, created_at FROM users WHERE email NOT LIKE "%@mmec.edu"')
    rows = cur.fetchall()
    conn.close()
    students = []
    for r in rows:
        name, email, marks, notes, created_at = r
        students.append({'name': name, 'email': email, 'marks': marks, 'notes': notes, 'registered': created_at})
    return jsonify({"ok": True, "students": students})

@app.route('/api/admin/update_student', methods=['POST'])
def api_admin_update_student():
    """Update student marks/notes."""
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or not user.endswith('@mmec.edu') or user not in ['admin1@mmec.edu', 'admin2@mmec.edu', 'admin3@mmec.edu', 'nidafazlinalband@gmail.com']:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    email = data.get('email')
    marks = data.get('marks')
    if not email:
        return jsonify({"ok": False, "error": "email required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('UPDATE users SET marks = ? WHERE email = ?', (marks, email))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/admin/history', methods=['GET'])
def api_admin_history():
    """Get chat history/logs."""
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    logs = load_logs()
    return jsonify({"ok": True, "history": logs})


@app.route('/api/admin/unanswered', methods=['GET'])
def api_admin_unanswered():
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT id, question, answer, answered, timestamp, answered_at, answered_by FROM unanswered_queries ORDER BY id DESC')
        rows = cur.fetchall()
        conn.close()
        out = []
        for r in rows:
            out.append({
                'id': r[0], 'question': r[1], 'answer': r[2], 'answered': bool(r[3] or 0), 'ts': r[4], 'answered_at': r[5], 'answered_by': r[6]
            })
        return jsonify({"ok": True, "unanswered": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/admin/answer_unanswered', methods=['POST'])
def api_admin_answer_unanswered():
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json() or {}
    qid = data.get('id')
    answer = data.get('answer')
    if not qid or not answer:
        return jsonify({"ok": False, "error": "missing parameters"}), 400
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Mark unanswered as answered
        cur.execute('UPDATE unanswered_queries SET answer=?, answered=1, answered_at=?, answered_by=? WHERE id=?', (answer, datetime.utcnow().isoformat() + 'Z', user, qid))
        # Insert into admin_faqs for future automatic replies
        cur.execute('INSERT INTO admin_faqs (question, answer, keywords, ts) VALUES (?, ?, ?, ?)', (data.get('question') or '', answer, data.get('keywords') or '', datetime.utcnow().isoformat() + 'Z'))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/admin/admin_faqs', methods=['GET','POST','DELETE'])
def api_admin_manage_faqs():
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if request.method == 'GET':
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('SELECT id, question, answer, keywords, ts FROM admin_faqs ORDER BY id DESC')
            rows = cur.fetchall()
            conn.close()
            out = [{'id': r[0], 'question': r[1], 'answer': r[2], 'keywords': r[3], 'ts': r[4]} for r in rows]
            return jsonify({"ok": True, "faqs": out})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    if request.method == 'POST':
        data = request.get_json() or {}
        question = data.get('question')
        answer = data.get('answer')
        keywords = data.get('keywords') or ''
        if not question or not answer:
            return jsonify({"ok": False, "error": "missing parameters"}), 400
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('INSERT INTO admin_faqs (question, answer, keywords, ts) VALUES (?, ?, ?, ?)', (question, answer, keywords, datetime.utcnow().isoformat() + 'Z'))
            conn.commit()
            conn.close()
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    if request.method == 'DELETE':
        data = request.get_json() or {}
        faq_id = data.get('id')
        if not faq_id:
            return jsonify({"ok": False, "error": "missing id"}), 400
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('DELETE FROM admin_faqs WHERE id=?', (faq_id,))
            conn.commit()
            conn.close()
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/admin/migrate_names', methods=['POST'])
def api_admin_migrate_names():
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, name, email FROM users')
    rows = cur.fetchall()
    updated = 0
    for r in rows:
        uid, name, email = r
        if (not name or name.strip() == '') and email:
            # infer name from email prefix
            prefix = email.split('@')[0]
            inferred = prefix.replace('.', ' ').replace('_', ' ').title()
            try:
                cur.execute('UPDATE users SET name=? WHERE id=?', (inferred, uid))
                updated += 1
            except Exception:
                continue
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "updated": updated})

@app.route('/api/admin/logins', methods=['GET'])
def api_admin_logins():
    """Get student login logs."""
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user or user not in ADMIN_EMAILS:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT name, email, login_time FROM logins JOIN users ON logins.user_id = users.id WHERE email NOT LIKE "%@mmec.edu" ORDER BY login_time DESC LIMIT 20')
    rows = cur.fetchall()
    conn.close()
    logins = [{'name': r[0], 'email': r[1], 'time': r[2]} for r in rows]
    return jsonify({"ok": True, "logins": logins})

@app.route('/api/admin/ai_status', methods=['GET'])
def api_admin_ai_status():
    """Get AI status for students."""
    token = get_token_from_request()
    user = SESSIONS.get(token)
    if not user:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    allow_external = is_external_allowed()
    return jsonify({"ok": True, "allow_external_queries": allow_external})

if __name__ == '__main__':
    # Ensure logs file exists
    if not os.path.exists(CHAT_LOG_FILE):
        with open(CHAT_LOG_FILE, 'w') as f:
            json.dump([], f)
    # Ensure users file exists (loaded by load_users)
    _ = load_users()
    # Initialize app databases
    init_db()
    init_mmec_db()
    app.run(host='0.0.0.0', port=5502, debug=True)
