from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
from functools import wraps
from database import init_db, get_db
import sqlite3
import re

app = Flask(__name__)

app.secret_key = "troque_essa_chave_secreta"

CORS(app, supports_credentials=True)

ADMIN_USER = "admin"
ADMIN_PASSWORD = "Admin@2026"

@app.route("/")
def home():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")

with app.app_context():
    init_db()


def validate_code(code):
    if not code or not isinstance(code, str):
        return False
    pattern = re.compile(r"^[A-Z0-9]{2,6}-[A-Z0-9]{2,6}$")
    return bool(pattern.match(code))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged"):
            return jsonify({"error": "Não autorizado. Faça login como administrador."}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "Nenhum dado enviado"}), 400

    username = data.get("username")
    password = data.get("password")

    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        session["admin_logged"] = True
        return jsonify({
            "success": True,
            "message": "Login realizado com sucesso"
        }), 200

    return jsonify({
        "success": False,
        "error": "Usuário ou senha inválidos"
    }), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logout realizado com sucesso"}), 200


@app.route("/api/check-auth", methods=["GET"])
def check_auth():
    return jsonify({"authenticated": bool(session.get("admin_logged"))}), 200


@app.route("/api/products", methods=["GET"])
def get_products():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products ORDER BY id DESC")
            products = cursor.fetchall()

            products_list = []
            for product in products:
                products_list.append({
                    "id": product["id"],
                    "code": product["code"],
                    "name": product["name"],
                    "description": product["description"],
                    "price": product["price"],
                    "quantity": product["quantity"],
                    "category": product["category"],
                    "created_at": product["created_at"]
                })

            return jsonify(products_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/products", methods=["POST"])
@login_required
def add_product():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Nenhum dado fornecido"}), 400

        required_fields = ["code", "name", "price", "quantity"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Campo obrigatório ausente: {field}"}), 400

        code = data["code"].strip().upper()

        if not validate_code(code):
            return jsonify({"error": "Código inválido. Use formato: BIK-001 ou PEC-123"}), 400

        try:
            price = float(data["price"])
            quantity = int(data["quantity"])
        except (ValueError, TypeError):
            return jsonify({"error": "Preço deve ser número e quantidade deve ser inteiro"}), 400

        if price < 0:
            return jsonify({"error": "Preço não pode ser negativo"}), 400

        if quantity < 0:
            return jsonify({"error": "Quantidade não pode ser negativa"}), 400

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM products WHERE code = ?", (code,))
            if cursor.fetchone():
                return jsonify({"error": f"Código {code} já está em uso"}), 400

            cursor.execute("""
                INSERT INTO products (code, name, description, price, quantity, category)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                code,
                data["name"],
                data.get("description", ""),
                price,
                quantity,
                data.get("category", "")
            ))

            product_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO stock_movements (product_id, quantity, type, observation)
                VALUES (?, ?, ?, ?)
            """, (
                product_id,
                quantity,
                "entry",
                f"Produto cadastrado com código {code}"
            ))

            conn.commit()

            return jsonify({
                "message": "Produto adicionado com sucesso",
                "id": product_id,
                "code": code
            }), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "Erro de integridade: código duplicado"}), 400
    except sqlite3.Error as e:
        return jsonify({"error": f"Erro no banco de dados: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500


@app.route("/api/products/<int:product_id>", methods=["PUT"])
@login_required
def update_product(product_id):
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Nenhum dado fornecido"}), 400

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id, quantity FROM products WHERE id = ?", (product_id,))
            product = cursor.fetchone()

            if not product:
                return jsonify({"error": "Produto não encontrado"}), 404

            updates = []
            values = []

            if "code" in data:
                new_code = data["code"].strip().upper()

                if not validate_code(new_code):
                    return jsonify({"error": "Código inválido. Use formato: BIK-001"}), 400

                cursor.execute(
                    "SELECT id FROM products WHERE code = ? AND id != ?",
                    (new_code, product_id)
                )

                if cursor.fetchone():
                    return jsonify({"error": f"Código {new_code} já está em uso"}), 400

                updates.append("code = ?")
                values.append(new_code)

            if "name" in data:
                updates.append("name = ?")
                values.append(data["name"])

            if "description" in data:
                updates.append("description = ?")
                values.append(data["description"])

            if "price" in data:
                try:
                    price = float(data["price"])
                    if price < 0:
                        return jsonify({"error": "Preço não pode ser negativo"}), 400

                    updates.append("price = ?")
                    values.append(price)

                except (ValueError, TypeError):
                    return jsonify({"error": "Preço deve ser um número válido"}), 400

            if "quantity" in data:
                try:
                    quantity = int(data["quantity"])

                    if quantity < 0:
                        return jsonify({"error": "Quantidade não pode ser negativa"}), 400

                    old_quantity = product["quantity"]
                    diff = quantity - old_quantity

                    if diff != 0:
                        movement_type = "entry" if diff > 0 else "exit"

                        cursor.execute("""
                            INSERT INTO stock_movements (product_id, quantity, type, observation)
                            VALUES (?, ?, ?, ?)
                        """, (
                            product_id,
                            abs(diff),
                            movement_type,
                            "Atualização manual de estoque"
                        ))

                    updates.append("quantity = ?")
                    values.append(quantity)

                except (ValueError, TypeError):
                    return jsonify({"error": "Quantidade deve ser um número inteiro"}), 400

            if "category" in data:
                updates.append("category = ?")
                values.append(data["category"])

            if not updates:
                return jsonify({"error": "Nenhum campo válido para atualizar"}), 400

            values.append(product_id)
            query = f'UPDATE products SET {", ".join(updates)} WHERE id = ?'
            cursor.execute(query, values)
            conn.commit()

            return jsonify({"message": "Produto atualizado com sucesso"}), 200

    except sqlite3.Error as e:
        return jsonify({"error": f"Erro no banco de dados: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
@login_required
def delete_product(product_id):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id, name, code FROM products WHERE id = ?", (product_id,))
            product = cursor.fetchone()

            if not product:
                return jsonify({"error": "Produto não encontrado"}), 404

            cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()

            return jsonify({
                "message": f'Produto "{product["name"]}" removido com sucesso'
            }), 200

    except sqlite3.Error as e:
        return jsonify({"error": f"Erro no banco de dados: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500


@app.route("/api/products/search", methods=["GET"])
def search_products():
    try:
        query = request.args.get("q", "")

        if not query:
            return get_products()

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM products
                WHERE code LIKE ? OR name LIKE ? OR category LIKE ? OR description LIKE ?
                ORDER BY id DESC
            """, (
                f"%{query}%",
                f"%{query}%",
                f"%{query}%",
                f"%{query}%"
            ))

            products = cursor.fetchall()

            products_list = []
            for product in products:
                products_list.append({
                    "id": product["id"],
                    "code": product["code"],
                    "name": product["name"],
                    "description": product["description"],
                    "price": product["price"],
                    "quantity": product["quantity"],
                    "category": product["category"],
                    "created_at": product["created_at"]
                })

            return jsonify(products_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/products/code/<string:product_code>", methods=["GET"])
def get_product_by_code(product_code):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM products WHERE code = ?",
                (product_code.upper(),)
            )

            product = cursor.fetchone()

            if not product:
                return jsonify({"error": f"Produto com código {product_code} não encontrado"}), 404

            return jsonify({
                "id": product["id"],
                "code": product["code"],
                "name": product["name"],
                "description": product["description"],
                "price": product["price"],
                "quantity": product["quantity"],
                "category": product["category"],
                "created_at": product["created_at"]
            }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stock/movements/<int:product_id>", methods=["GET"])
def get_stock_movements(product_id):
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM stock_movements
                WHERE product_id = ?
                ORDER BY created_at DESC
            """, (product_id,))

            movements = cursor.fetchall()

            movements_list = []
            for movement in movements:
                movements_list.append({
                    "id": movement["id"],
                    "product_id": movement["product_id"],
                    "quantity": movement["quantity"],
                    "type": movement["type"],
                    "observation": movement["observation"],
                    "created_at": movement["created_at"]
                })

            return jsonify(movements_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Servidor Flask rodando corretamente"
    }), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)