from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)
db_path = "cafe_app.db"

def get_db_connection():
    """データベース接続を取得"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    """ホームページ（仮）"""
    return render_template('home.html')

@app.route('/product/add', methods=['GET', 'POST'])
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

        return redirect(url_for('add_product'))
    
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

@app.route('/transaction', methods=['GET', 'POST'])
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
        change = int(request.form['change'])
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

    print(logs)  # << ここで取得データをターミナルに表示

    return render_template('transaction_history.html', logs=logs)

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
