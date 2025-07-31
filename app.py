# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import urllib.request
import urllib.parse
import ssl
import base64
from flask_wtf import CSRFProtect
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired
from dotenv import load_dotenv
import os
import sys
import json

# Зареждане на .env файла
load_dotenv()

# Проверка за критични .env променливи
required_env_vars = [
    'EMAIL_USER', 'EMAIL_PASS',
    'TWILIO_SID', 'TWILIO_AUTH', 'TWILIO_FROM',
    'FLASK_SECRET_KEY'
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    print("\n❌ ГРЕШКА: Липсват критични конфигурационни променливи")
    print("Моля, създайте .env файл със следните променливи:")
    for var in missing_vars:
        print(f"- {var}")
    
    # Създаване на шаблонен .env файл ако не съществува
    if not os.path.exists('.env'):
        try:
            with open('.env', 'w', encoding='utf-8') as f:
                f.write("# Автоматично генериран .env файл\n")
                for var in missing_vars:
                    f.write(f"{var}=трябва_да_попълните_тук\n")
            print("\n✔ Създаден е шаблонен .env файл. Моля, попълнете липсващите стойности!")
        except Exception as e:
            print(f"\n⚠ Неуспешно създаване на .env файл: {str(e)}")
    
    sys.exit(1)

# Flask приложение и CSRF защита
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
csrf = CSRFProtect(app)

# Имейл конфигурация от .env
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

# WTForms форма за състезатели
class PlayerForm(FlaskForm):
    name = StringField('Име на състезателя', validators=[DataRequired()])
    age = IntegerField('Възраст', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired()])
    submit = SubmitField('Запази')

# Инициализация на базата данни
def init_db():
    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players
                 (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, phone TEXT, email TEXT, 
                  parent_name TEXT, parent_phone TEXT, parent_email TEXT, active INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY, player_id INTEGER, month TEXT, year INTEGER, 
                  paid INTEGER DEFAULT 0, FOREIGN KEY(player_id) REFERENCES players(id))''')
    conn.commit()
    conn.close()

init_db()

# Помощни функции за плащания
def get_current_month():
    months = ["Януари", "Февруари", "Март", "Април", "Май", "Юни", 
              "Юли", "Август", "Септември", "Октомври", "Ноември", "Декември"]
    return months[datetime.now().month - 1]

def get_payment_history(player_id):
    db = sqlite3.connect('volleyball.db')
    cursor = db.cursor()
    result = cursor.execute(
        "SELECT month, year FROM payments WHERE player_id = ? ORDER BY year DESC, month DESC",
        (player_id,)
    ).fetchall()
    db.close()
    return result

def check_payment_status(player_id, month, year):
    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    c.execute("SELECT paid FROM payments WHERE player_id=? AND month=? AND year=?", 
              (player_id, month, year))
    result = c.fetchone()
    conn.close()
    return bool(result and result[0]) if result else False

# Контекстни процесори за шаблоните
@app.context_processor
def utility_processor():
    return dict(
        current_year=datetime.now().year,
        current_month=get_current_month(),
        check_payment_status=check_payment_status
    )

@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Функция за изпращане на SMS чрез Twilio API
def send_sms_via_twilio(to_number, message_body):
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH')
    TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM')

    url = f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json'

    data = urllib.parse.urlencode({
        'From': TWILIO_FROM_NUMBER,
        'To': to_number,
        'Body': message_body
    }).encode('utf-8')

    credentials = f'{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}'
    base64_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    req = urllib.request.Request(url, data)
    req.add_header("Authorization", f"Basic {base64_credentials}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(req, context=context) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"✅ SMS изпратен успешно. SID: {result.get('sid')}")
            return True
    except urllib.error.HTTPError as e:
        try:
            error_content = e.read().decode('utf-8') if e.fp else ''
            error_msg = json.loads(error_content).get('message', str(e)) if error_content else str(e)
        except Exception:
            error_msg = str(e)
        print(f"⚠️ HTTP грешка при изпращане на SMS: {error_msg}")
    except Exception as e:
        print(f"⚠️ Неочаквана грешка при изпращане на SMS: {str(e)}")

    return False

# Функция за изпращане на имейл
def send_email(to, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = to

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"✅ Имейл изпратен успешно до {to}")
        return True
    except Exception as e:
        print(f"⚠️ Грешка при изпращане на имейл до {to}: {str(e)}")
        return False

# Главна страница с филтриране на състезатели и статус на плащанията
@app.route('/')
def home():
    name_filter = request.args.get('name', '').strip()
    age_filter = request.args.get('age', '').strip()
    status_filter = request.args.get('status', '').strip()

    conn = sqlite3.connect('volleyball.db')
    cursor = conn.cursor()

    query = "SELECT * FROM players WHERE active=1"
    params = []

    if name_filter:
        query += " AND name LIKE ?"
        params.append(f"%{name_filter}%")
    if age_filter:
        query += " AND age = ?"
        params.append(age_filter)

    players = cursor.execute(query, params).fetchall()

    current_month = get_current_month()
    current_year = datetime.now().year

    if status_filter in ['paid', 'unpaid']:
        filtered_players = []
        for p in players:
            paid = check_payment_status(p[0], current_month, current_year)
            if (status_filter == 'paid' and paid) or (status_filter == 'unpaid' and not paid):
                filtered_players.append(p)
        players = filtered_players

    histories = {p[0]: get_payment_history(p[0]) for p in players}

    conn.close()

    return render_template('index.html',
                           players=players,
                           histories=histories,
                           current_month=current_month,
                           current_year=current_year)

# Добавяне на нов състезател
@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        try:
            player_data = (
                request.form['name'],
                int(request.form['age']),
                request.form['phone'],
                request.form.get('email', ''),
                request.form['parent_name'],
                request.form['parent_phone'],
                request.form.get('parent_email', '')
            )
            
            conn = sqlite3.connect('volleyball.db')
            c = conn.cursor()
            c.execute("""INSERT INTO players 
                         (name, age, phone, email, parent_name, parent_phone, parent_email)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""", player_data)
            conn.commit()
            conn.close()
            
            flash('Състезателят е добавен успешно!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'Грешка при добавяне: {str(e)}', 'error')
    
    return render_template('add_player.html')

# Редактиране на състезател
@app.route('/edit_player/<int:player_id>', methods=['GET', 'POST'])
def edit_player(player_id):
    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        try:
            player_data = (
                request.form['name'],
                int(request.form['age']),
                request.form['phone'],
                request.form.get('email', ''),
                request.form['parent_name'],
                request.form['parent_phone'],
                request.form.get('parent_email', ''),
                player_id
            )
            
            c.execute("""UPDATE players SET 
                         name=?, age=?, phone=?, email=?, 
                         parent_name=?, parent_phone=?, parent_email=?
                         WHERE id=?""", player_data)
            conn.commit()
            flash('Данните са обновени успешно!', 'success')
            conn.close()
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'Грешка при обновяване: {str(e)}', 'error')
            conn.close()
    
    c.execute("SELECT * FROM players WHERE id=?", (player_id,))
    player = c.fetchone()
    conn.close()
    
    if not player:
        flash('Състезателят не е намерен!', 'error')
        return redirect(url_for('home'))
    
    return render_template('edit_player.html', player=player)

@app.route('/check_payment', methods=['GET'])
def check_payment():
    player_id = request.args.get('player_id')
    month = request.args.get('month')
    year = request.args.get('year')

    if not player_id or not month or not year:
        return jsonify({'error': 'Missing parameters'}), 400

    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    c.execute("SELECT paid FROM payments WHERE player_id=? AND month=? AND year=?", 
              (player_id, month, year))
    result = c.fetchone()
    conn.close()

    return jsonify({'paid': bool(result and result[0])})

@app.route('/mark_payment', methods=['POST'])
def mark_payment():
    data = request.get_json()
    player_id = data.get('player_id')
    month = data.get('month')
    year = data.get('year')

    if not player_id or not month or not year:
        return jsonify({'error': 'Missing data'}), 400

    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO payments 
                 (player_id, month, year, paid) 
                 VALUES (?, ?, ?, ?)""", (player_id, month, year, 1))
    conn.commit()

    c.execute("SELECT name, phone FROM players WHERE id = ?", (player_id,))
    player = c.fetchone()
    conn.close()

    if not player:
        return jsonify({'error': 'Играчът не е намерен'}), 404

    name, phone = player
    message = f"{name}, Вашата такса за {month} {year} е маркирана като платена. Благодарим ви!"

    sms_sent = send_sms_via_twilio(phone, message)

    return jsonify({'status': 'marked', 'sms_sent': sms_sent})


# Обработка на плащане (примерно)
@app.route('/payment/<int:player_id>', methods=['POST'])
def payment(player_id):
    month = request.form.get('month')
    year = int(request.form.get('year', datetime.now().year))
    
    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO payments (player_id, month, year, paid) VALUES (?, ?, ?, ?)",
              (player_id, month, year, 1))

    # Вземане на телефонен номер на състезателя
    c.execute("SELECT name, phone FROM players WHERE id=?", (player_id,))
    player = c.fetchone()
    conn.commit()
    conn.close()

    # Изпращане на SMS
    if player and player[1]:
        sms_message = f"Здравей, {player[0]}! Плащането за {month} {year} е прието успешно. Благодарим!"
        send_sms_via_twilio(player[1], sms_message)

    flash('Плащането е маркирано като извършено.', 'success')
    return redirect(url_for('home'))

@app.route('/send_reminder', methods=['POST'])
def send_reminder():
    data = request.get_json()
    player_id = data.get('player_id')

    if not player_id:
        return jsonify({'error': 'Missing player_id'}), 400

    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    c.execute("SELECT name, phone FROM players WHERE id = ?", (player_id,))
    player = c.fetchone()
    conn.close()

    if not player:
        return jsonify({'error': 'Player not found'}), 404

    name, phone = player
    phone = normalize_phone(phone)

    message = f"{name}, напомняме Ви да платите месечната си такса. Благодарим Ви!"
    sms_sent = send_sms_via_twilio(phone, message)

    return jsonify({'reminder_sent': sms_sent})

@app.route('/trigger_reminders', methods=['POST'])
def trigger_reminders():
    month = datetime.now().month
    year = datetime.now().year

    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.name, p.phone FROM players p
        LEFT JOIN payments pay ON p.id = pay.player_id 
        AND pay.month = ? AND pay.year = ?
        WHERE pay.paid IS NULL OR pay.paid = 0
    """, (month, year))
    players = c.fetchall()
    conn.close()

    reminders_sent = []
    for pid, name, phone in players:
        phone = normalize_phone(phone)
        message = f"{name}, напомняме Ви да платите таксата за {month}/{year}. Благодарим Ви!"
        success = send_sms_via_twilio(phone, message)
        reminders_sent.append({'player_id': pid, 'success': success})

    return jsonify({'reminders': reminders_sent})

def normalize_phone(phone):
    # Преобразува български номера от 0878... към +359878...
    if phone.startswith('0'):
        return '+359' + phone[1:]
    return phone


# Основно стартиране на приложението
if __name__ == '__main__':
    app.run(debug=True)
