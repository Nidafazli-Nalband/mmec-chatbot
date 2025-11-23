"""Lightweight db_utils stub for the MMEC prototype.
This provides simple functions used by the Flask admin endpoints.
For production replace with real DB access (SQLite/Postgres) and proper validation.
"""
import json
import os

DATA_FILE = os.path.join('data', 'db_stub.json')

# ensure data folder
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

# Initialize a basic structure if missing
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'general_info': {'name': 'Maratha Mandal Engineering College', 'location': 'Belagavi'},
            'courses': {},
            'faculty': {},
            'fee_structure': {},
            'timetable': {}
        }, f, indent=2)


def _read():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write(d):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=2)


# Read helpers
def get_general_info():
    return _read().get('general_info', {})


def get_courses():
    return _read().get('courses', {})


def get_faculty():
    return _read().get('faculty', {})


def get_fee_structure():
    return _read().get('fee_structure', {})


def get_timetable():
    return _read().get('timetable', {})

# Update / delete helpers - basic implementations that return True on success

def update_general_info(key, value):
    d = _read()
    d.setdefault('general_info', {})[key] = value
    _write(d)
    return True


def delete_general_info(key):
    d = _read()
    if 'general_info' in d and key in d['general_info']:
        d['general_info'].pop(key)
        _write(d)
        return True
    return False


def update_course(course_code, course_name, details):
    d = _read()
    d.setdefault('courses', {})[course_code] = {'name': course_name, 'details': details}
    _write(d)
    return True


def delete_course(course_code):
    d = _read()
    if 'courses' in d and course_code in d['courses']:
        d['courses'].pop(course_code)
        _write(d)
        return True
    return False


def update_faculty(faculty_id, name, department, details):
    d = _read()
    d.setdefault('faculty', {})[faculty_id] = {'name': name, 'department': department, 'details': details}
    _write(d)
    return True


def delete_faculty(faculty_id):
    d = _read()
    if 'faculty' in d and faculty_id in d['faculty']:
        d['faculty'].pop(faculty_id)
        _write(d)
        return True
    return False


def update_fee_structure(course_type, amount, details):
    d = _read()
    d.setdefault('fee_structure', {})[course_type] = {'amount': amount, 'details': details}
    _write(d)
    return True


def delete_fee_structure(course_type):
    d = _read()
    if 'fee_structure' in d and course_type in d['fee_structure']:
        d['fee_structure'].pop(course_type)
        _write(d)
        return True
    return False


def update_timetable(day, time_slot, course_id, faculty_id, room):
    d = _read()
    d.setdefault('timetable', {}).setdefault(day, {})[time_slot] = {'course_id': course_id, 'faculty_id': faculty_id, 'room': room}
    _write(d)
    return True


def delete_timetable(day, time_slot, course_id):
    d = _read()
    if 'timetable' in d and day in d['timetable'] and time_slot in d['timetable'][day]:
        d['timetable'][day].pop(time_slot)
        _write(d)
        return True
    return False
