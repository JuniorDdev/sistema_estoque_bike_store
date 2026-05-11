from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import io
import re

from flask import Flask, Response, jsonify, make_response, render_template, request, session
from flask_cors import CORS
from functools import wraps
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from config import Config
from extensions import db, migrate
from models import Product, Sale, SaleItem, StockMovement

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, supports_credentials=True)

db.init_app(app)
migrate.init_app(app, db)

ADMIN_USER = "testezila"
ADMIN_PASSWORD = "testezila@123"


def validate_code(code):
    if not code or not isinstance(code, str):
        return False
    pattern = re.compile(r"^[A-Z0-9]{2,6}-[A-Z0-9]{2,6}$")
    return bool(pattern.match(code))


def normalize_decimal_price(value):
    try:
        price = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if price < 0:
        return None

    return price


def normalize_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return None

    if quantity < 0:
        return None

    return quantity


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged"):
            return jsonify({"error": "Nao autorizado. Faca login como administrador."}), 401
        return f(*args, **kwargs)

    return decorated_function


def get_period_range(period):
    now = datetime.now()
    if period == "day":
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
        label = "Dia"
        return start, end, label

    if period == "month":
        start = datetime(now.year, now.month, 1)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1)
        else:
            end = datetime(now.year, now.month + 1, 1)
        label = "Mes"
        return start, end, label

    return None, None, None


def get_sales_report(period):
    start, end, label = get_period_range(period)
    if not start:
        return None

    sales = (
        Sale.query.options(joinedload(Sale.items).joinedload(SaleItem.product))
        .filter(Sale.created_at >= start, Sale.created_at < end)
        .order_by(Sale.created_at.desc())
        .all()
    )

    total_sales = len(sales)
    total_revenue = sum((sale.total_amount for sale in sales), Decimal("0.00"))
    total_items = sum(item.quantity for sale in sales for item in sale.items)
    average_ticket = total_revenue / total_sales if total_sales > 0 else Decimal("0.00")

    return {
        "period": period,
        "period_label": label,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "summary": {
            "total_sales": total_sales,
            "total_revenue": float(total_revenue),
            "total_items": total_items,
            "average_ticket": float(average_ticket.quantize(Decimal("0.01"))),
        },
        "sales": [sale.to_dict() for sale in sales],
    }


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


@app.route("/loja")
def loja():
    return render_template("loja.html")


@app.route("/relatorio")
def relatorio():
    return render_template("relatorio.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "Nenhum dado enviado"}), 400

    username = data.get("username")
    password = data.get("password")

    if username == ADMIN_USER and password == ADMIN_PASSWORD:
        session["admin_logged"] = True
        return jsonify({"success": True, "message": "Login realizado com sucesso"}), 200

    return jsonify({"success": False, "error": "Usuario ou senha invalidos"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logout realizado com sucesso"}), 200


@app.route("/api/check-auth", methods=["GET"])
def check_auth():
    return jsonify({"authenticated": bool(session.get("admin_logged"))}), 200


@app.route("/api/products", methods=["GET"])
def get_products():
    products = Product.query.order_by(Product.id.desc()).all()
    return jsonify([product.to_dict() for product in products]), 200


@app.route("/api/products", methods=["POST"])
@login_required
def add_product():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Nenhum dado fornecido"}), 400

    required_fields = ["code", "name", "price", "quantity"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Campo obrigatorio ausente: {field}"}), 400

    code = str(data["code"]).strip().upper()

    if not validate_code(code):
        return jsonify({"error": "Codigo invalido. Use formato: BIK-001 ou PEC-123"}), 400

    if Product.query.filter_by(code=code).first():
        return jsonify({"error": f"Codigo {code} ja esta em uso"}), 400

    price = normalize_decimal_price(data["price"])
    if price is None:
        return jsonify({"error": "Preco deve ser numero valido e nao negativo"}), 400

    quantity = normalize_quantity(data["quantity"])
    if quantity is None:
        return jsonify({"error": "Quantidade deve ser inteiro valido e nao negativo"}), 400

    product = Product(
        code=code,
        name=str(data["name"]).strip(),
        description=str(data.get("description", "")).strip(),
        price=price,
        quantity=quantity,
        category=str(data.get("category", "")).strip(),
    )

    db.session.add(product)
    db.session.flush()

    movement = StockMovement(
        product_id=product.id,
        quantity=quantity,
        type="entry",
        observation=f"Produto cadastrado com codigo {code}",
    )
    db.session.add(movement)
    db.session.commit()

    return jsonify({"message": "Produto adicionado com sucesso", "id": product.id, "code": code}), 201


@app.route("/api/products/<int:product_id>", methods=["PUT"])
@login_required
def update_product(product_id):
    data = request.get_json()

    if not data:
        return jsonify({"error": "Nenhum dado fornecido"}), 400

    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Produto nao encontrado"}), 404

    if "code" in data:
        new_code = str(data["code"]).strip().upper()
        if not validate_code(new_code):
            return jsonify({"error": "Codigo invalido. Use formato: BIK-001"}), 400

        exists = Product.query.filter(Product.code == new_code, Product.id != product_id).first()
        if exists:
            return jsonify({"error": f"Codigo {new_code} ja esta em uso"}), 400
        product.code = new_code

    if "name" in data:
        product.name = str(data["name"]).strip()

    if "description" in data:
        product.description = str(data["description"]).strip()

    if "price" in data:
        price = normalize_decimal_price(data["price"])
        if price is None:
            return jsonify({"error": "Preco deve ser um numero valido e nao negativo"}), 400
        product.price = price

    if "quantity" in data:
        quantity = normalize_quantity(data["quantity"])
        if quantity is None:
            return jsonify({"error": "Quantidade deve ser um numero inteiro valido"}), 400

        diff = quantity - product.quantity
        if diff != 0:
            movement = StockMovement(
                product_id=product.id,
                quantity=abs(diff),
                type="entry" if diff > 0 else "exit",
                observation="Atualizacao manual de estoque",
            )
            db.session.add(movement)

        product.quantity = quantity

    if "category" in data:
        product.category = str(data["category"]).strip()

    db.session.commit()
    return jsonify({"message": "Produto atualizado com sucesso"}), 200


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
@login_required
def delete_product(product_id):
    try:
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify({"error": "Produto nao encontrado"}), 404

        sales_count = db.session.query(func.count(SaleItem.id)).filter(SaleItem.product_id == product.id).scalar()
        if sales_count and sales_count > 0:
            return jsonify({"error": "Nao e possivel excluir: produto possui historico de vendas"}), 400

        product_name = product.name
        db.session.delete(product)
        db.session.commit()

        return jsonify({"message": f'Produto "{product_name}" removido com sucesso'}), 200
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Erro no banco ao excluir produto"}), 500
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Erro interno ao excluir produto"}), 500


@app.route("/api/products/search", methods=["GET"])
def search_products():
    query = request.args.get("q", "").strip()

    if not query:
        return get_products()

    like = f"%{query}%"
    products = (
        Product.query.filter(
            or_(
                Product.code.ilike(like),
                Product.name.ilike(like),
                Product.category.ilike(like),
                Product.description.ilike(like),
            )
        )
        .order_by(Product.id.desc())
        .all()
    )

    return jsonify([product.to_dict() for product in products]), 200


@app.route("/api/store/products/search", methods=["GET"])
def search_store_products():
    query = request.args.get("q", "").strip()
    like = f"%{query}%"

    products_query = Product.query.filter(Product.quantity > 0)
    if query:
        products_query = products_query.filter(or_(Product.code.ilike(like), Product.name.ilike(like)))

    products = products_query.order_by(Product.name.asc()).limit(20).all()
    return jsonify([product.to_dict() for product in products]), 200


@app.route("/api/store/sales", methods=["POST"])
@login_required
def create_sale():
    data = request.get_json() or {}
    items_payload = data.get("items", [])

    if not items_payload:
        return jsonify({"error": "Nenhum item informado para venda"}), 400

    parsed_items = []
    product_ids = []
    for item in items_payload:
        product_id = item.get("product_id")
        quantity = normalize_quantity(item.get("quantity"))
        if not product_id or quantity is None or quantity <= 0:
            return jsonify({"error": "Itens invalidos. Informe produto e quantidade maior que zero"}), 400
        parsed_items.append({"product_id": int(product_id), "quantity": quantity})
        product_ids.append(int(product_id))

    products = Product.query.filter(Product.id.in_(product_ids)).all()
    products_by_id = {product.id: product for product in products}

    for item in parsed_items:
        product = products_by_id.get(item["product_id"])
        if not product:
            return jsonify({"error": f"Produto ID {item['product_id']} nao encontrado"}), 404
        if product.quantity < item["quantity"]:
            return jsonify({"error": f"Estoque insuficiente para {product.name}"}), 400

    total_amount = Decimal("0.00")
    sale = Sale(total_amount=Decimal("0.00"))
    db.session.add(sale)
    db.session.flush()

    for item in parsed_items:
        product = products_by_id[item["product_id"]]
        line_total = (product.price * item["quantity"]).quantize(Decimal("0.01"))
        total_amount += line_total

        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=item["quantity"],
            unit_price=product.price,
            line_total=line_total,
        )
        db.session.add(sale_item)

        product.quantity -= item["quantity"]
        movement = StockMovement(
            product_id=product.id,
            quantity=item["quantity"],
            type="exit",
            observation=f"Venda #{sale.id}",
        )
        db.session.add(movement)

    sale.total_amount = total_amount.quantize(Decimal("0.01"))
    db.session.commit()

    sale = db.session.get(Sale, sale.id, options=[joinedload(Sale.items).joinedload(SaleItem.product)])
    return jsonify({"message": "Venda registrada com sucesso", "sale": sale.to_dict()}), 201


@app.route("/api/reports/sales", methods=["GET"])
def sales_report():
    period = request.args.get("period", "day").lower()
    report_data = get_sales_report(period)
    if not report_data:
        return jsonify({"error": "Periodo invalido. Use day ou month"}), 400
    return jsonify(report_data), 200


@app.route("/api/reports/sales/export", methods=["GET"])
def export_sales_report():
    period = request.args.get("period", "day").lower()
    fmt = request.args.get("format", "csv").lower()

    report_data = get_sales_report(period)
    if not report_data:
        return jsonify({"error": "Periodo invalido. Use day ou month"}), 400

    now_label = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_base = f"relatorio_vendas_{period}_{now_label}"

    rows = []
    for sale in report_data["sales"]:
        for item in sale["items"]:
            rows.append([
                sale["id"],
                sale["created_at"],
                item["product_code"],
                item["product_name"],
                item["quantity"],
                item["unit_price"],
                item["line_total"],
            ])

    headers = ["Venda ID", "Data", "Codigo", "Produto", "Quantidade", "Preco Unitario", "Total Linha"]

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)
        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f"attachment; filename={filename_base}.csv"
        return response

    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Vendas"
        ws.append(headers)
        bold_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = bold_font
        for row in rows:
            ws.append(row)

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)

        return Response(
            stream.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.xlsx"},
        )

    if fmt == "pdf":
        stream = io.BytesIO()
        pdf = canvas.Canvas(stream, pagesize=A4)
        width, height = A4

        y = height - 40
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, y, f"Relatorio de Vendas - {report_data['period_label']}")
        y -= 30

        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y, f"Total de vendas: {report_data['summary']['total_sales']}")
        y -= 15
        pdf.drawString(40, y, f"Receita total: R$ {report_data['summary']['total_revenue']:.2f}")
        y -= 25

        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(40, y, "Venda")
        pdf.drawString(90, y, "Codigo")
        pdf.drawString(160, y, "Produto")
        pdf.drawString(360, y, "Qtd")
        pdf.drawString(400, y, "Unit.")
        pdf.drawString(470, y, "Total")

        y -= 15
        pdf.setFont("Helvetica", 8)
        for row in rows:
            if y < 40:
                pdf.showPage()
                y = height - 40
                pdf.setFont("Helvetica", 8)
            pdf.drawString(40, y, str(row[0]))
            pdf.drawString(90, y, str(row[2]))
            pdf.drawString(160, y, str(row[3])[:35])
            pdf.drawString(360, y, str(row[4]))
            pdf.drawString(400, y, f"{float(row[5]):.2f}")
            pdf.drawString(470, y, f"{float(row[6]):.2f}")
            y -= 12

        pdf.save()
        stream.seek(0)

        return Response(
            stream.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"},
        )

    return jsonify({"error": "Formato invalido. Use csv, xlsx ou pdf"}), 400


@app.route("/api/products/code/<string:product_code>", methods=["GET"])
def get_product_by_code(product_code):
    product = Product.query.filter_by(code=product_code.upper()).first()

    if not product:
        return jsonify({"error": f"Produto com codigo {product_code} nao encontrado"}), 404

    return jsonify(product.to_dict()), 200


@app.route("/api/stock/movements/<int:product_id>", methods=["GET"])
def get_stock_movements(product_id):
    movements = (
        StockMovement.query.filter_by(product_id=product_id)
        .order_by(StockMovement.created_at.desc())
        .all()
    )
    return jsonify([movement.to_dict() for movement in movements]), 200


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Servidor Flask rodando corretamente"}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
