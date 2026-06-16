from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def _now():
    return datetime.now(timezone.utc)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    articles = db.relationship(
        "Article",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="Article.created_at.desc()",
    )

    @property
    def published_articles(self):
        return [a for a in self.articles if a.published]


class Article(db.Model):
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(300), default="")
    body = db.Column(db.Text, default="")  # Markdown（HTML 混在可）
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True
    )
    published = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    category = db.relationship("Category", back_populates="articles")


class AdminUser(UserMixin, db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LoginThrottle(db.Model):
    """ログイン失敗回数を記録し、総当たり攻撃をロックアウトする。

    既存テーブルを変更せず新規テーブルとして追加するため、Alembic 等の
    マイグレーション無しで db.create_all() だけで導入できる。
    """

    __tablename__ = "login_throttle"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    failed_count = db.Column(db.Integer, default=0, nullable=False)
    last_failed_at = db.Column(db.DateTime(timezone=True), default=_now)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
