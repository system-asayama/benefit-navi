from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required, login_user, logout_user

from extensions import db
from models import AdminUser, Article, Category
from utils import unique_slug

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(request.args.get("next") or url_for("admin.dashboard"))
        flash("ユーザー名またはパスワードが違います。", "error")
    return render_template("admin/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("ログアウトしました。", "success")
    return redirect(url_for("admin.login"))


@bp.route("/")
@login_required
def dashboard():
    articles = Article.query.order_by(Article.updated_at.desc()).all()
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template(
        "admin/dashboard.html", articles=articles, categories=categories
    )


# ---- 記事 CRUD ---------------------------------------------------------------


@bp.route("/articles/new", methods=["GET", "POST"])
@login_required
def article_new():
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("タイトルは必須です。", "error")
            return render_template(
                "admin/article_form.html",
                categories=categories,
                article=None,
                form=request.form,
            )
        art = Article(
            title=title,
            summary=request.form.get("summary", "").strip(),
            body=request.form.get("body", ""),
            category_id=int(request.form["category_id"]),
            published=bool(request.form.get("published")),
        )
        slug_input = request.form.get("slug", "").strip() or title
        art.slug = unique_slug(slug_input, Article, fallback="article")
        db.session.add(art)
        db.session.commit()
        flash("記事を作成しました。", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template(
        "admin/article_form.html", categories=categories, article=None, form={}
    )


@bp.route("/articles/<int:article_id>/edit", methods=["GET", "POST"])
@login_required
def article_edit(article_id):
    art = db.session.get(Article, article_id)
    if art is None:
        abort(404)
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("タイトルは必須です。", "error")
            return render_template(
                "admin/article_form.html",
                categories=categories,
                article=art,
                form=request.form,
            )
        art.title = title
        art.summary = request.form.get("summary", "").strip()
        art.body = request.form.get("body", "")
        art.category_id = int(request.form["category_id"])
        art.published = bool(request.form.get("published"))
        slug_input = request.form.get("slug", "").strip() or title
        art.slug = unique_slug(
            slug_input, Article, fallback="article", current_id=art.id
        )
        db.session.commit()
        flash("記事を更新しました。", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template(
        "admin/article_form.html", categories=categories, article=art, form={}
    )


@bp.route("/articles/<int:article_id>/delete", methods=["POST"])
@login_required
def article_delete(article_id):
    art = db.session.get(Article, article_id)
    if art is None:
        abort(404)
    db.session.delete(art)
    db.session.commit()
    flash("記事を削除しました。", "success")
    return redirect(url_for("admin.dashboard"))


# ---- カテゴリ管理 ------------------------------------------------------------


@bp.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("カテゴリ名は必須です。", "error")
        else:
            cat = Category(
                name=name,
                description=request.form.get("description", "").strip(),
                sort_order=int(request.form.get("sort_order") or 0),
            )
            cat.slug = unique_slug(
                request.form.get("slug", "").strip() or name,
                Category,
                fallback="category",
            )
            db.session.add(cat)
            db.session.commit()
            flash("カテゴリを追加しました。", "success")
        return redirect(url_for("admin.categories"))
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template("admin/categories.html", categories=cats)


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def category_delete(category_id):
    cat = db.session.get(Category, category_id)
    if cat is None:
        abort(404)
    if cat.articles:
        flash("記事が残っているカテゴリは削除できません。", "error")
        return redirect(url_for("admin.categories"))
    db.session.delete(cat)
    db.session.commit()
    flash("カテゴリを削除しました。", "success")
    return redirect(url_for("admin.categories"))
