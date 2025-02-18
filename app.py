from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # セキュリティキーを設定
db_path = "cafe_app.db"

def get_db_connection():
    """データベース接続を取得"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/register', methods=['GET', 'POST'])
def register():
    """ユーザー登録ページ"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        if not username or not password or role not in ['admin', 'member']:
            flash("すべての項目を正しく入力してください", "error")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)  # パスワードをハッシュ化

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           (username, hashed_password, role))  # ハッシュ化したパスワードを保存
            conn.commit()
            flash("ユーザー登録が完了しました", "success")
        except sqlite3.IntegrityError:
            flash("このユーザー名はすでに登録されています", "error")
        finally:
            conn.close()

        return redirect(url_for('home'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """ログインページ"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash("ログインに成功しました", "success")
            return redirect(url_for('home'))
        else:
            flash("ユーザー名またはパスワードが間違っています", "error")
    
    return render_template('login.html')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("ログインが必要です", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/logout')
def logout():
    """ログアウト処理"""
    session.clear()
    flash("ログアウトしました", "success")
    return redirect(url_for('login'))

@app.route('/')
def home():
    """ホームページ"""
    return render_template('home.html')

@app.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """商品を登録する"""
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        unit_price = request.form['unit_price']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products (name, description, category, unit_price, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (name, description, category, unit_price)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('products'))
    
    return render_template('add_product.html')

@app.route('/products')
def products():
    """商品一覧を表示"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """商品情報を編集"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        unit_price = request.form['unit_price']

        cursor.execute(
            "UPDATE products SET name=?, description=?, category=?, unit_price=? WHERE id=?",
            (name, description, category, unit_price, product_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('products'))

    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()

    return render_template('edit_product.html', product=product)

@app.route('/product/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """商品を削除"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('products'))

@app.route('/transaction', methods=['GET', 'POST'])
@login_required
def transaction():
    """商品を入出庫する"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 商品リストを取得
    cursor.execute("SELECT id, name FROM products")
    products = cursor.fetchall()

    if request.method == 'POST':
        product_id = request.form['product_id']
        action = request.form['action']
        change = int(request.form['change'])  # 'change' に修正
        notes = request.form.get('notes', '')

        # 入庫 or 出庫処理
        cursor.execute("SELECT quantity FROM stock WHERE product_id = ?", (product_id,))
        stock_entry = cursor.fetchone()

        if stock_entry:
            new_quantity = stock_entry['quantity'] + change if action == '入庫' else stock_entry['quantity'] - change
            if new_quantity < 0:
                new_quantity = 0  # 在庫はマイナスにならないようにする
            cursor.execute("UPDATE stock SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?", (new_quantity, product_id))
        else:
            if action == '入庫':  # 在庫がない場合は入庫のみ可能
                cursor.execute("INSERT INTO stock (product_id, quantity, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (product_id, change))

        # 履歴を記録
        cursor.execute(
            "INSERT INTO inventory_log (product_id, user_id, change, action, timestamp, notes) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (product_id, 1, change, action, notes)  # ユーザーIDは仮で 1 に設定
        )

        conn.commit()
        conn.close()
        return redirect(url_for('transaction'))

    conn.close()
    return render_template('transaction.html', products=products)

@app.route('/transaction_history')
def transaction_history():
    """入出庫履歴を表示"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT inventory_log.id, products.name, inventory_log.action, 
               inventory_log.change, inventory_log.timestamp, inventory_log.notes
        FROM inventory_log
        JOIN products ON inventory_log.product_id = products.id
        ORDER BY inventory_log.timestamp DESC
    """)
    logs = cursor.fetchall()
    conn.close()

    return render_template('transaction_history.html', logs=logs)

@app.route('/transaction_history/edit/<int:log_id>', methods=['GET', 'POST'])
def edit_transaction(log_id):
    """入出庫履歴を編集"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        change = int(request.form['change'])
        action = request.form['action']
        notes = request.form.get('notes', '')

        cursor.execute(
            "UPDATE inventory_log SET change = ?, action = ?, notes = ? WHERE id = ?",
            (change, action, notes, log_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('transaction_history'))

    cursor.execute("SELECT * FROM inventory_log WHERE id = ?", (log_id,))
    log = cursor.fetchone()
    conn.close()

    return render_template('edit_transaction.html', log=log)

@app.route('/transaction_history/delete/<int:log_id>', methods=['POST'])
def delete_transaction(log_id):
    """入出庫履歴を削除"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory_log WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('transaction_history'))

@app.route('/stock')
def stock():
    """在庫一覧を表示"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT products.id, products.name, IFNULL(stock.quantity, 0) AS quantity, stock.updated_at
        FROM products
        LEFT JOIN stock ON products.id = stock.product_id
    """)
    stocks = cursor.fetchall()
    conn.close()
    return render_template('stock.html', stocks=stocks)

if __name__ == '__main__':
    app.run(debug=True)
