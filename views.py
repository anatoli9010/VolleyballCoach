from flask import Flask, request, jsonify
from database import init_db
import sqlite3

app = Flask(__name__)

@app.route('/check_payment')
def check_payment_status():
    player_id = request.args.get('player_id')
    month = request.args.get('month')
    year = request.args.get('year')

    if not player_id or not month or not year:
        return jsonify({'error': 'Липсват параметри'}), 400

    conn = sqlite3.connect('volleyball.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM payments WHERE player_id=? AND month=? AND year=?''',
                   (player_id, month, year))
    payment = cursor.fetchone()
    conn.close()

    if payment:
        return jsonify({'paid': True})
    else:
        return jsonify({'paid': False}), 404
