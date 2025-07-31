# test_check_payment.py
import unittest
import json
from app import app, init_db
import sqlite3

class CheckPaymentTestCase(unittest.TestCase):
    def setUp(self):
        # Настройка преди всеки тест
        self.app = app.test_client()
        self.app.testing = True

        # Създаваме тестов играч и плащане в базата
        init_db()
        self.conn = sqlite3.connect('volleyball.db')
        self.cursor = self.conn.cursor()

        # Добавяме играч
        self.cursor.execute("INSERT INTO players (name, age, phone, active) VALUES (?, ?, ?, ?)",
                            ("Тест Играч", 15, "0888123456", 1))
        self.player_id = self.cursor.lastrowid

        # Добавяме плащане
        self.cursor.execute("INSERT INTO payments (player_id, month, year, paid) VALUES (?, ?, ?, ?)",
                            (self.player_id, "Юли", 2025, 1))
        self.conn.commit()

    def tearDown(self):
        # Почистване след всеки тест
        self.cursor.execute("DELETE FROM payments WHERE player_id=?", (self.player_id,))
        self.cursor.execute("DELETE FROM players WHERE id=?", (self.player_id,))
        self.conn.commit()
        self.conn.close()

    def test_check_payment_success(self):
        response = self.app.get(f'/check_payment?player_id={self.player_id}&month=Юли&year=2025')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['paid'])

    def test_check_payment_not_paid(self):
        response = self.app.get(f'/check_payment?player_id={self.player_id}&month=Август&year=2025')
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertFalse(data['paid'])

    def test_check_payment_missing_params(self):
        response = self.app.get('/check_payment')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('Липсват параметри', data['error'])

if __name__ == '__main__':
    unittest.main()
