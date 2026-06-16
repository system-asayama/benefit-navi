from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from extensions import db
from models import AdminUser, Article, Category, LoginThrottle
from utils import unique_slug

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _now():
    return datetime.now(timezone.utc)


def _as_aware(dt):
    """DB から取得した datetime を UTC aware に正規化する（SQLite は naive を返す）。"""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_safe_url(target):
    """next パラメータがこのサイト内への相対/同一ホスト URL かを検証する。

    外部 URL を弾くことでオープンリダイレクト（フィッシング誘導）を防ぐ。
    """
    if not target:
        return False
    host_url = request.host_url
    test = urlparse(urljoin(host_url, target))
    return test.scheme in ("http", "https") and urlparse(host_url).netloc == test.netloc


def _lockout_remaining_minutes(throttle):
    """ロック中なら残り分数（切り上げ）を返す。ロックされていなければ 0。"""
    if throttle is None or throttle.locked_until is None:
        return 0
    locked_until = _as_aware(throttle.locked_until)
    if locked_until <= _now():
        return 0
    return int((locked_until - _now()).total_seconds() // 60) + 1


def _register_failed_attempt(username):
    """ログイン失敗を記録し、規定回数を超えたらロックアウトする。"""
    if not username:
        return
    throttle = LoginThrottle.query.filter_by(username=username).first()
    if throttle is None:
        throttle = LoginThrottle(username=username, failed_count=0)
        db.session.add(throttle)
    throttle.failed_count = (throttle.failed_count or 0) + 1
    throttle.last_failed_at = _now()
    if throttle.failed_count >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
        minutes = current_app.config["LOGIN_LOCKOUT_MINUTES"]
        throttle.locked_until = _now() + timedelta(minutes=minutes)
        throttle.failed_count = 0  # ロック後はカウンタをリセット
    db.session.commit()


def _clear_throttle(username):
    LoginThrottle.query.filter_by(username=username).delete()
    db.session.commit()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        throttle = LoginThrottle.query.filter_by(username=username).first()
        remaining = _lockout_remaining_minutes(throttle)
        if remaining:
            flash(
                f"ログイン試行が多すぎます。約{remaining}分後に再度お試しください。",
                "error",
            )
            return render_template("admin/login.html")

        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            _clear_throttle(username)
            login_user(user, remember=bool(request.form.get("remember")))
            next_url = request.args.get("next")
            if not is_safe_url(next_url):
                next_url = None
            flash("ログインしました。", "success")
            return redirect(next_url or url_for("admin.dashboard"))

        _register_failed_attempt(username)
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


# ---- 管理者ユーザー管理 ------------------------------------------------------


@bp.route("/users", methods=["GET", "POST"])
@login_required
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("password_confirm", "")
        min_len = current_app.config["ADMIN_PASSWORD_MIN_LENGTH"]

        if not username or not password:
            flash("ユーザー名とパスワードは必須です。", "error")
        elif password != confirm:
            flash("確認用パスワードが一致しません。", "error")
        elif len(password) < min_len:
            flash(f"パスワードは{min_len}文字以上にしてください。", "error")
        elif AdminUser.query.filter_by(username=username).first():
            flash("そのユーザー名は既に使われています。", "error")
        else:
            user = AdminUser(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f"管理者「{username}」を追加しました。", "success")
        return redirect(url_for("admin.users"))

    admins = AdminUser.query.order_by(AdminUser.username).all()
    return render_template("admin/users.html", admins=admins)


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def user_delete(user_id):
    user = db.session.get(AdminUser, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash("自分自身は削除できません。", "error")
        return redirect(url_for("admin.users"))
    if AdminUser.query.count() <= 1:
        flash("管理者が1人だけのため削除できません。", "error")
        return redirect(url_for("admin.users"))

    username = user.username
    db.session.delete(user)
    LoginThrottle.query.filter_by(username=username).delete()
    db.session.commit()
    flash(f"管理者「{username}」を削除しました。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/password", methods=["POST"])
@login_required
def user_password(user_id):
    """自分のパスワードを変更する。他ユーザーのパスワードは変更不可。"""
    if user_id != current_user.id:
        abort(403)
    user = db.session.get(AdminUser, user_id)
    if user is None:
        abort(404)

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("new_password_confirm", "")
    min_len = current_app.config["ADMIN_PASSWORD_MIN_LENGTH"]

    if not user.check_password(current_password):
        flash("現在のパスワードが違います。", "error")
    elif new_password != confirm:
        flash("確認用パスワードが一致しません。", "error")
    elif len(new_password) < min_len:
        flash(f"パスワードは{min_len}文字以上にしてください。", "error")
    else:
        user.set_password(new_password)
        db.session.commit()
        flash("パスワードを変更しました。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/username", methods=["POST"])
@login_required
def user_username(user_id):
    """自分のログインID（ユーザー名）を変更する。確認のため現在のパスワードを要求。"""
    if user_id != current_user.id:
        abort(403)
    user = db.session.get(AdminUser, user_id)
    if user is None:
        abort(404)

    new_username = request.form.get("new_username", "").strip()
    current_password = request.form.get("current_password", "")

    if not user.check_password(current_password):
        flash("現在のパスワードが違います。", "error")
    elif not new_username:
        flash("新しいログインIDを入力してください。", "error")
    elif new_username == user.username:
        flash("現在のログインIDと同じです。", "error")
    elif AdminUser.query.filter_by(username=new_username).first():
        flash("そのログインIDは既に使われています。", "error")
    else:
        old_username = user.username
        user.username = new_username
        # 旧IDに紐づくロック記録は不要になるため掃除する
        LoginThrottle.query.filter_by(username=old_username).delete()
        db.session.commit()
        flash(f"ログインIDを「{new_username}」に変更しました。", "success")
    return redirect(url_for("admin.users"))
