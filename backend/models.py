from decimal import Decimal

from extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    category = db.Column(db.String(120), nullable=False, default="")
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    stock_movements = db.relationship(
        "StockMovement",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="desc(StockMovement.created_at)",
    )
    sale_items = db.relationship("SaleItem", back_populates="product")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "price": float(self.price) if isinstance(self.price, Decimal) else self.price,
            "quantity": self.quantity,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    observation = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    product = db.relationship("Product", back_populates="stock_movements")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "type": self.type,
            "observation": self.observation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    items = db.relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleItem.id.asc()",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "total_amount": float(self.total_amount) if isinstance(self.total_amount, Decimal) else self.total_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items],
        }


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product", back_populates="sale_items")

    def to_dict(self):
        return {
            "id": self.id,
            "sale_id": self.sale_id,
            "product_id": self.product_id,
            "product_code": self.product.code if self.product else None,
            "product_name": self.product.name if self.product else None,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price) if isinstance(self.unit_price, Decimal) else self.unit_price,
            "line_total": float(self.line_total) if isinstance(self.line_total, Decimal) else self.line_total,
        }
