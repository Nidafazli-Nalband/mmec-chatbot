import sqlite3
import os

DB_PATH = os.path.join('data', 'mmec.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_general_info():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT key, value FROM general_info')
    rows = cur.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def update_general_info(key, value):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO general_info (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
    return True

def delete_general_info(key):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM general_info WHERE key = ?', (key,))
    conn.commit()
    conn.close()
    return True

def get_courses():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT course_code, course_name, details FROM courses')
    rows = cur.fetchall()
    conn.close()
    return [{'course_code': row[0], 'course_name': row[1], 'details': row[2]} for row in rows]

def update_course(course_code, course_name, details):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO courses (course_code, course_name, details) VALUES (?, ?, ?)', (course_code, course_name, details))
    conn.commit()
    conn.close()
    return True

def delete_course(course_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM courses WHERE course_code = ?', (course_code,))
    conn.commit()
    conn.close()
    return True

def get_faculty():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT faculty_id, name, department, details FROM faculty')
    rows = cur.fetchall()
    conn.close()
    return [{'faculty_id': row[0], 'name': row[1], 'department': row[2], 'details': row[3]} for row in rows]

def update_faculty(faculty_id, name, department, details):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO faculty (faculty_id, name, department, details) VALUES (?, ?, ?, ?)', (faculty_id, name, department, details))
    conn.commit()
    conn.close()
    return True

def delete_faculty(faculty_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM faculty WHERE faculty_id = ?', (faculty_id,))
    conn.commit()
    conn.close()
    return True

def get_fee_structure():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT course_type, amount, details FROM fee_structure')
    rows = cur.fetchall()
    conn.close()
    return [{'course_type': row[0], 'amount': row[1], 'details': row[2]} for row in rows]

def update_fee_structure(course_type, amount, details):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO fee_structure (course_type, amount, details) VALUES (?, ?, ?)', (course_type, amount, details))
    conn.commit()
    conn.close()
    return True

def delete_fee_structure(course_type):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM fee_structure WHERE course_type = ?', (course_type,))
    conn.commit()
    conn.close()
    return True

def get_timetable():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT day, time_slot, course_id, faculty_id, room FROM timetable')
    rows = cur.fetchall()
    conn.close()
    return [{'day': row[0], 'time_slot': row[1], 'course_id': row[2], 'faculty_id': row[3], 'room': row[4]} for row in rows]

def update_timetable(day, time_slot, course_id, faculty_id, room):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO timetable (day, time_slot, course_id, faculty_id, room) VALUES (?, ?, ?, ?, ?)', (day, time_slot, course_id, faculty_id, room))
    conn.commit()
    conn.close()
    return True

def delete_timetable(day, time_slot, course_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM timetable WHERE day = ? AND time_slot = ? AND course_id = ?', (day, time_slot, course_id))
    conn.commit()
    conn.close()
    return True
