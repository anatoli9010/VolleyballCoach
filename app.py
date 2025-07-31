# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
import sqlite3
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
from openpyxl import Workbook
from io import BytesIO
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
from flask import request, jsonify
from app import app


# 1. Първо зареждаме .env файла
load_dotenv()

# 2. Дефинираме необходимите променливи
required_env_vars = [
    'EMAIL_USER', 'EMAIL_PASS',
    'TWILIO_SID', 'TWILIO_AUTH', 'TWILIO_FROM',
    'FLASK_SECRET_KEY'
]

# 3. Проверяваме кои променливи липсват
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

# 4. Обработка на липсващите променливи
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

# Останалият код на приложението...


# Проверка дали всички нужни .env променливи са зададени
required_env_vars = [
    'EMAIL_USER', 'EMAIL_PASS',
    'TWILIO_SID', 'TWILIO_AUTH', 'TWILIO_FROM',
    'FLASK_SECRET_KEY'
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    print(f"\n\u274C Липсват следните .env променливи: {', '.join(missing_vars)}\n")
    sys.exit(1)

class PlayerForm(FlaskForm):
    name = StringField('Име на състезателя', validators=[DataRequired()])
    age = IntegerField('Възраст', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired()])
    submit = SubmitField('Запази')

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
csrf = CSRFProtect(app)

# Имейл конфигурация от .env
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

# Функция за изпращане на SMS чрез Twilio

def send_sms_via_twilio(to_number, message_body):
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH')
    TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM')

    url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'

    data = urllib.parse.urlencode({
        'From': from_number,
        'To': to_number,
        'Body': message_body
    }).encode('utf-8')

    credentials = f'{account_sid}:{auth_token}'
    base64_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

    request = urllib.request.Request(url, data)
    request.add_header("Authorization", f"Basic {base64_credentials}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    context = ssl._create_unverified_context()

    try:
        response = urllib.request.urlopen(request, context=context)
        result = response.read().decode('utf-8')
        print("\u2705 SMS изпратен успешно: {}".format(result).encode('ascii', 'ignore').decode('ascii'))
        return True
    except Exception as e:
        print("\u26a0\ufe0f Грешка при изпращане на SMS: {}".format(e).encode('ascii', 'ignore').decode('ascii'))
        return False

# Останалият код остава непроменен освен ако няма нужда от допълнителна защита


# Инициализация на DB
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

@app.route('/')
def home():
    name_filter = request.args.get('name', '').strip()
    age_filter = request.args.get('age', '').strip()
    status_filter = request.args.get('status', '').strip()

    db = sqlite3.connect('volleyball.db')
    cursor = db.cursor()

    query = "SELECT * FROM players WHERE 1=1"
    params = []

    if name_filter:
        query += " AND name LIKE ?"
        params.append("%{}%".format(name_filter))
    if age_filter:
        query += " AND age = ?"
        params.append(age_filter)

    players = cursor.execute(query, params).fetchall()

    # Статус на плащане (платил/неплатил)
    current_month = datetime.now().strftime('%B')
    current_year = datetime.now().year

    if status_filter in ['paid', 'unpaid']:
        filtered_players = []
        for p in players:
            paid = check_payment_status(p[0], current_month, current_year)
            if status_filter == 'paid' and paid:
                filtered_players.append(p)
            elif status_filter == 'unpaid' and not paid:
                filtered_players.append(p)
        players = filtered_players

    # История на плащанията
    histories = {p[0]: get_payment_history(p[0]) for p in players}

    return render_template('index.html',
                           players=players,
                           histories=histories,
                           current_month=current_month,
                           current_year=current_year)


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
            flash('Грешка при добавяне: {0}'.format(str(e)), 'error')
    
    return render_template('add_player.html')

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
            return redirect(url_for('home'))
        except Exception as e:
            flash('Грешка при обновяване: {0}'.format(str(e)), 'error')
    
    c.execute("SELECT * FROM players WHERE id=?", (player_id,))
    player = c.fetchone()
    conn.close()
    
    if not player:
        flash('Състезателят не е намерен!', 'error')
        return redirect(url_for('home'))
    
    return render_template('edit_player.html', player=player)

@app.route('/delete_player/<int:player_id>')
def delete_player(player_id):
    try:
        conn = sqlite3.connect('volleyball.db')
        c = conn.cursor()
        c.execute("UPDATE players SET active=0 WHERE id=?", (player_id,))
        conn.commit()
        conn.close()
        flash('Състезателят е архивиран успешно!', 'success')
    except Exception as e:
        flash('Грешка при архивиране: {0}'.format(str(e)), 'error')
    
    return redirect(url_for('home'))

@app.route('/send_reminder', methods=['POST'])
def send_reminder():
    data = request.json
    phone = data['phone']
    player_id = data['player_id']

    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()

    try:
        # Тук извикваш функцията за изпращане на SMS (примерно send_sms_via_twilio)
        sms_result = send_sms_via_twilio(phone, "Напомняне за плащане на месечна такса")
        print("SMS изпратен успешно:", sms_result)

        # Имейл съобщение
        msg = MIMEText("Напомняне за плащане на месечна такса")
        msg['Subject'] = 'Волейболен клуб - напомняне'
        msg['From'] = EMAIL_USER
        msg['To'] = '{}@vivatel.bg'.format(phone)

        # Имейл до родителя
        c.execute("SELECT parent_email FROM players WHERE id=?", (player_id,))
        row = c.fetchone()
        parent_email = row[0] if row else None

        if parent_email:
            msg2 = MIMEText("Уважаеми родителю,\n\nНапомняме Ви за дължима месечна такса.\n\nПоздрави,\nВолейболен клуб")
            msg2['Subject'] = 'Напомняне за месечна такса'
            msg2['From'] = EMAIL_USER
            msg2['To'] = parent_email
        else:
            msg2 = None

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        if msg2:
            server.send_message(msg2)
        server.quit()

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        print("Грешка при изпращане на напомняне:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        conn.close()

def send_sms_via_twilio(to_number, message_body):
    """Изпраща SMS чрез Twilio API"""
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_FROM_NUMBER')
        
        if not all([account_sid, auth_token, from_number]):
            raise ValueError("Липсват Twilio конфигурационни данни в .env файла")

        # Подготвяне на заявката
        url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
        
        data = urllib.parse.urlencode({
            'From': from_number,
            'To': to_number,
            'Body': message_body
        }).encode('utf-8')

        # Автентикация
        credentials = f'{account_sid}:{auth_token}'.encode('utf-8')
        base64_credentials = base64.b64encode(credentials).decode('utf-8')

        # Създаване на заявка
        req = urllib.request.Request(url, data)
        req.add_header("Authorization", f"Basic {base64_credentials}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        # SSL контекст (по-безопасна версия)
        context = ssl.create_default_context()

        # Изпращане на заявка
        with urllib.request.urlopen(req, context=context) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"✅ SMS изпратен успешно. SID: {result.get('sid')}")
            return True
            
    except urllib.error.HTTPError as e:
        error_msg = json.loads(e.read().decode('utf-8')).get('message', str(e))
        print(f"⚠️ HTTP грешка при изпращане на SMS: {error_msg}")
    except Exception as e:
        print(f"⚠️ Неочаквана грешка: {str(e)}")
    
    return False

# Изпращане на потвърждение за платена такса (SMS + имейл до родител)
def send_payment_confirmation(player_id, month, year):
    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()

    # Изпращане на SMS
    c.execute("SELECT parent_phone FROM players WHERE id=?", (player_id,))
    phone = c.fetchone()[0]
    message_body = f"Потвърждение за платена такса за {month} {year}"
    send_sms_via_twilio(phone, message_body)

    # Изпращане на имейл до родител
    c.execute("SELECT parent_email FROM players WHERE id=?", (player_id,))
    parent_email = c.fetchone()[0]

    if parent_email:
        try:
            msg = MIMEText(f"Благодарим ви! Плащането за {month} {year} е прието успешно.")
            msg['Subject'] = 'Потвърждение за плащане'
            msg['From'] = EMAIL_USER
            msg['To'] = parent_email

            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print("⚠️ Неуспешно изпращане на имейл до родител:", e)

    conn.close()

@app.route('/mark_payment', methods=['POST'])
def mark_payment():
    data = request.json
    conn = sqlite3.connect('volleyball.db')
    c = conn.cursor()

    try:
        c.execute("SELECT id FROM payments WHERE player_id=? AND month=? AND year=?",
                  (data['player_id'], data['month'], data['year']))
        payment = c.fetchone()

        if payment:
            c.execute("UPDATE payments SET paid=1 WHERE id=?", (payment[0],))
        else:
            c.execute("INSERT INTO payments (player_id, month, year, paid) VALUES (?, ?, ?, 1)",
                      (data['player_id'], data['month'], data['year']))

        conn.commit()

        # Изпращане на SMS и имейл до родител
        send_payment_confirmation(data['player_id'], data['month'], data['year'])

        return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

    finally:
        conn.close()

@app.route('/check_payment')
def check_payment():
    player_id = request.args.get('player_id')
    month = request.args.get('month')
    year = request.args.get('year')

    if not player_id or not month or not year:
        return jsonify({'error': 'Липсват параметри'}), 400

    try:
        paid = check_payment_status(int(player_id), month, int(year))
        if paid:
            return jsonify({'paid': True})
        else:
            return jsonify({'paid': False}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("⏳ Стартиране на сървър...")
    app.run(host='0.0.0.0', port=5000, debug=True)
    print("🛑 Сървърът спря")
