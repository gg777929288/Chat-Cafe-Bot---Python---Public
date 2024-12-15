import os
import sqlite3
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

def convert_to_sql(report_data, sql_file_path):
    conn = sqlite3.connect(sql_file_path)
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_number TEXT,
            reporter_id TEXT,
            reported_id TEXT,
            violation_type TEXT,
            violation_reason TEXT,
            channel TEXT,
            time TEXT,
            evidence TEXT,
            timestamp TEXT,
            hash TEXT
        )''')
        conn.execute('''INSERT INTO reports (
            case_number, reporter_id, reported_id, violation_type, violation_reason, channel, time, evidence, timestamp, hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', report_data)
    conn.close()

@app.route('/api/reports', methods=['GET'])
def get_reports():
    conn = sqlite3.connect('path_to_your_sql_file.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reports')
    reports = cursor.fetchall()
    conn.close()
    return jsonify(reports)

@app.route('/api/sql-files', methods=['GET'])
def list_sql_files():
    sql_files = [f for f in os.listdir('D:/Chat-Cafe-Bot---Python/Userfile/reports') if f.endswith('.sql')]
    return jsonify(sql_files)

@app.route('/api/sql-files/<filename>', methods=['GET'])
def get_sql_file(filename):
    return send_from_directory('D:/Chat-Cafe-Bot---Python/Userfile/reports', filename)

if __name__ == '__main__':
    app.run(debug=True)
