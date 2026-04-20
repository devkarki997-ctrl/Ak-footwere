import os
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "ak_footwear_ultra_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ak_inventory.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads/')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, shoe_name TEXT, color TEXT, price REAL, stock INTEGER, image TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, date_time TEXT, item_details TEXT, customer_name TEXT, customer_phone TEXT, qty INTEGER, unit_price REAL, total REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)')
    
    if not cursor.execute('SELECT * FROM users WHERE id=1').fetchone():
        cursor.execute('INSERT INTO users (id, username, password) VALUES (1, "admin", "1234")')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- LOGIN & SECURITY ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username=? AND password=?', 
                            (request.form['username'], request.form['password'])).fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            return redirect(url_for('index'))
        return "Invalid Credentials! <a href='/login'>Try again</a>"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/update_creds', methods=['POST'])
def update_creds():
    if not session.get('logged_in'): return redirect(url_for('login'))
    current_pass = request.form['current_password']
    new_user = request.form['new_username']
    new_pass = request.form['new_password']
    conn = get_db_connection()
    user = conn.execute('SELECT password FROM users WHERE id=1').fetchone()
    if user['password'] == current_pass:
        conn.execute('UPDATE users SET username=?, password=? WHERE id=1', (new_user, new_pass))
        conn.commit()
        conn.close()
        session.pop('logged_in', None)
        return "<h1>Success!</h1> Login updated. Please <a href='/login'>Login again</a>."
    conn.close()
    return "<h1>Error!</h1> Current password wrong. <a href='/'>Go back</a>"

# --- MAIN SHOP PAGES ---
@app.route('/')
def index():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    items = conn.execute("SELECT DISTINCT shoe_name, image FROM inventory GROUP BY shoe_name").fetchall()
    all_inventory = conn.execute("SELECT * FROM inventory ORDER BY shoe_name ASC").fetchall()
    conn.close()
    return render_template('index.html', items=items, all_inventory=all_inventory)

@app.route('/add_shoe', methods=['POST'])
def add_shoe():
    if not session.get('logged_in'): return redirect(url_for('login'))
    name = request.form['name']
    color = request.form['color']
    price = request.form['price']
    stock = request.form['stock']
    file = request.files.get('image')
    
    filename = "default.jpg"
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    conn = get_db_connection()
    conn.execute('INSERT INTO inventory (shoe_name, color, price, stock, image) VALUES (?, ?, ?, ?, ?)',
                 (name, color, price, stock, filename))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/place_order', methods=['POST'])
def place_order():
    data = request.json
    conn = get_db_connection()
    item = conn.execute('SELECT stock, price FROM inventory WHERE shoe_name=? AND color=?', (data['shoe_name'], data['color'])).fetchone()
    qty = int(data['qty'])
    
    if item and item['stock'] >= qty:
        total = qty * item['price']
        conn.execute('UPDATE inventory SET stock = stock - ? WHERE shoe_name=? AND color=?', (qty, data['shoe_name'], data['color']))
        conn.execute('INSERT INTO sales (date_time, item_details, customer_name, customer_phone, qty, unit_price, total) VALUES (?,?,?,?,?,?,?)', 
                     (datetime.now().strftime("%Y-%m-%d %H:%M"), f"{data['shoe_name']} ({data['color']})", data['customer_name'], data['customer_phone'], qty, item['price'], total))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    conn.close()
    return jsonify({"status": "error", "message": "Out of stock!"})

@app.route('/history')
def history():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    sales = conn.execute("SELECT * FROM sales ORDER BY id DESC").fetchall()
    grand_total = conn.execute("SELECT SUM(total) FROM sales").fetchone()[0] or 0
    conn.close()
    return render_template('history.html', sales=sales, grand_total=grand_total)

@app.route('/get_colors/<name>')
def get_colors(name):
    conn = get_db_connection()
    colors = conn.execute('SELECT color, stock, price FROM inventory WHERE shoe_name = ?', (name,)).fetchall()
    conn.close()
    return jsonify([dict(c) for c in colors])

@app.route('/delete_item/<int:id>')
def delete_item(id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM inventory WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)