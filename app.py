from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import json
import os
import threading
import time
import requests

app = Flask(__name__)

STORAGE_FILE = 'uid_storage.json'
storage_lock = threading.Lock()

def ensure_storage_file():
    if not os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'w') as file:
            json.dump({}, file)

def load_uids():
    ensure_storage_file()
    with open(STORAGE_FILE, 'r') as file:
        return json.load(file)

def save_uids(uids):
    ensure_storage_file()
    with open(STORAGE_FILE, 'w') as file:
        json.dump(uids, file, default=str)

def cleanup_expired_uids():
    while True:
        with storage_lock:
            uids = load_uids()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            expired_uids = [uid for uid, exp_time in uids.items() if exp_time != 'permanent' and exp_time <= current_time]
            for uid in expired_uids:
                requests.get(f"https://remove-xza-1.onrender.com/panel_remove?uid={uid}")
                del uids[uid]
                print(f"Deleted expired UID: {uid}")
            save_uids(uids)
        time.sleep(1)

# بدء الخيط الخاص بالتنظيف
cleanup_thread = threading.Thread(target=cleanup_expired_uids, daemon=True)
cleanup_thread.start()

@app.route('/add_uid', methods=['GET', 'POST'])
def add_uid():
    uid = request.args.get('uid') or request.form.get('uid')
    time_value = request.args.get('time') or request.form.get('time')
    time_unit = request.args.get('type') or request.form.get('type')
    permanent = (request.args.get('permanent') or request.form.get('permanent') or 'false').lower() == 'true'

    if not uid:
        return jsonify({'error': 'Missing parameter: uid'}), 400

    if permanent:
        expiration_time = 'permanent'
        requests.get(f"https://xza-add.onrender.com/panel_add?uid={uid}")
    else:
        if not time_value or not time_unit:
            return jsonify({'error': 'Missing parameters: time or type'}), 400
        try:
            time_value = int(time_value)
        except ValueError:
            return jsonify({'error': 'Invalid time value. Must be an integer.'}), 400

        current_time = datetime.now()
        if time_unit == 'days':
            expiration_time = current_time + timedelta(days=time_value)
        elif time_unit == 'months':
            expiration_time = current_time + timedelta(days=time_value * 30)
        elif time_unit == 'years':
            expiration_time = current_time + timedelta(days=time_value * 365)
        elif time_unit == 'seconds':
            expiration_time = current_time + timedelta(seconds=time_value)
        else:
            return jsonify({'error': 'Invalid type. Use "days", "months", "years", or "seconds".'}), 400

        expiration_time = expiration_time.strftime('%Y-%m-%d %H:%M:%S')
        requests.get(f"https://xza-add.onrender.com/panel_add?uid={uid}")

    with storage_lock:
        uids = load_uids()
        uids[uid] = expiration_time
        save_uids(uids)

    return jsonify({
        'uid': uid,
        'expires_at': expiration_time if not permanent else 'never'
    })

@app.route('/get_time', methods=['GET', 'POST'])
def check_time():
    uid = request.args.get('uid') or request.form.get('uid')
    if not uid:
        return jsonify({'error': 'Missing UID'}), 400

    with storage_lock:
        uids = load_uids()
        if uid not in uids:
            return jsonify({'error': 'UID not found'}), 404

        expiration_time = uids[uid]
        if expiration_time == 'permanent':
            return jsonify({
                'uid': uid,
                'status': 'permanent',
                'message': 'This UID will never expire.'
            })

        expiration_time = datetime.strptime(expiration_time, '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        if current_time > expiration_time:
            return jsonify({'error': 'UID has expired'}), 400

        remaining_time = expiration_time - current_time
        days = remaining_time.days
        hours, remainder = divmod(remaining_time.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return jsonify({
            'uid': uid,
            'remaining_time': {
                'days': days,
                'hours': hours,
                'minutes': minutes,
                'seconds': seconds
            }
        })

if __name__ == '__main__':
    ensure_storage_file()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))