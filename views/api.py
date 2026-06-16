"""MCP 連携用の REST API。

すべて Bearer トークン認証。API_TOKEN が未設定のときは API を無効化する。
"""

from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models import Article, Category, LandingPage
from utils import unique_slug

bp = Blueprint("api", __name__, url_prefix="/api")


def require_token(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        token = current_app.config.get("API_TOKEN", "")
        if not token:
            return jsonify(error="API is disabled (API_TOKEN not set)"), 503
        auth = request.headers.get("Authorization", "")
        provided = auth[7:] if auth.startswith("Bearer ") else ""
        if provided != token:
            return jsonify(error="unauthorized"), 401
        return view(*args, **kwargs)

    return wrapper


def category_dict(c):
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description or "",
        "sort_order": c.sort_order,
        "article_count": len(c.articles),
    }


def article_dict(a, body=True):
    data = {
        "id": a.id,
        "title": a.title,
        "slug": a.slug,
        "summary": a.summary or "",
        "category": {"id": a.category.id, "name": a.category.name, "slug": a.category.slug},
        "published": a.published,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "url": f"/article/{a.slug}",
    }
    if body:
        data["body"] = a.body or ""
    return data


def _resolve_category(payload):
    """payload から Category を特定する。category_id か category(slug/name) を受け付ける。"""
    if payload.get("category_id") is not None:
        return db.session.get(Category, int(payload["category_id"]))
    ref = payload.get("category")
    if ref:
        return (
            Category.query.filter_by(slug=str(ref)).first()
            or Category.query.filter_by(name=str(ref)).first()
        )
    return None


# ---- categories --------------------------------------------------------------


@bp.get("/categories")
@require_token
def list_categories():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    return jsonify([category_dict(c) for c in cats])


@bp.post("/categories")
@require_token
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name is required"), 400
    if Category.query.filter_by(name=name).first():
        return jsonify(error="category already exists"), 409
    cat = Category(
        name=name,
        description=(data.get("description") or "").strip(),
        sort_order=int(data.get("sort_order") or 0),
    )
    cat.slug = unique_slug(data.get("slug") or name, Category, fallback="category")
    db.session.add(cat)
    db.session.commit()
    return jsonify(category_dict(cat)), 201


# ---- articles ----------------------------------------------------------------


@bp.get("/articles")
@require_token
def list_articles():
    query = Article.query
    cat_ref = request.args.get("category")
    if cat_ref:
        cat = (
            Category.query.filter_by(slug=cat_ref).first()
            or Category.query.filter_by(name=cat_ref).first()
        )
        if cat is None:
            return jsonify(error="category not found"), 404
        query = query.filter_by(category_id=cat.id)
    published = request.args.get("published")
    if published is not None:
        query = query.filter_by(published=published.lower() in ("1", "true", "yes"))
    articles = query.order_by(Article.updated_at.desc()).all()
    return jsonify([article_dict(a, body=False) for a in articles])


@bp.get("/articles/<slug>")
@require_token
def get_article(slug):
    art = Article.query.filter_by(slug=slug).first()
    if art is None:
        return jsonify(error="article not found"), 404
    return jsonify(article_dict(art))


@bp.post("/articles")
@require_token
def create_article():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(error="title is required"), 400
    cat = _resolve_category(data)
    if cat is None:
        return jsonify(error="category not found (use 'category' slug/name or 'category_id')"), 400
    art = Article(
        title=title,
        summary=(data.get("summary") or "").strip(),
        body=data.get("body") or "",
        category_id=cat.id,
        published=bool(data.get("published", True)),
    )
    art.slug = unique_slug(data.get("slug") or title, Article, fallback="article")
    db.session.add(art)
    db.session.commit()
    return jsonify(article_dict(art)), 201


@bp.patch("/articles/<int:article_id>")
@require_token
def update_article(article_id):
    art = db.session.get(Article, article_id)
    if art is None:
        return jsonify(error="article not found"), 404
    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify(error="title cannot be empty"), 400
        art.title = title
    if "summary" in data:
        art.summary = (data.get("summary") or "").strip()
    if "body" in data:
        art.body = data.get("body") or ""
    if "published" in data:
        art.published = bool(data.get("published"))
    if data.get("category") or data.get("category_id") is not None:
        cat = _resolve_category(data)
        if cat is None:
            return jsonify(error="category not found"), 400
        art.category_id = cat.id
    if data.get("slug"):
        art.slug = unique_slug(data["slug"], Article, fallback="article", current_id=art.id)
    db.session.commit()
    return jsonify(article_dict(art))


@bp.post("/articles/<int:article_id>/publish")
@require_token
def publish_article(article_id):
    art = db.session.get(Article, article_id)
    if art is None:
        return jsonify(error="article not found"), 404
    art.published = True
    db.session.commit()
    return jsonify(article_dict(art, body=False))


@bp.post("/articles/<int:article_id>/unpublish")
@require_token
def unpublish_article(article_id):
    art = db.session.get(Article, article_id)
    if art is None:
        return jsonify(error="article not found"), 404
    art.published = False
    db.session.commit()
    return jsonify(article_dict(art, body=False))


@bp.delete("/articles/<int:article_id>")
@require_token
def delete_article(article_id):
    art = db.session.get(Article, article_id)
    if art is None:
        return jsonify(error="article not found"), 404
    db.session.delete(art)
    db.session.commit()
    return jsonify(deleted=article_id)


# ---- landing pages -----------------------------------------------------------
# 記事と違い、保存した HTML をそのまま /lp/<slug> で配信する独自デザインの LP。


def landing_dict(lp, html=True):
    data = {
        "id": lp.id,
        "title": lp.title,
        "slug": lp.slug,
        "published": lp.published,
        "created_at": lp.created_at.isoformat() if lp.created_at else None,
        "updated_at": lp.updated_at.isoformat() if lp.updated_at else None,
        "url": f"/lp/{lp.slug}",
    }
    if html:
        data["html"] = lp.html or ""
    return data


@bp.get("/landing-pages")
@require_token
def list_landing_pages():
    query = LandingPage.query
    published = request.args.get("published")
    if published is not None:
        query = query.filter_by(published=published.lower() in ("1", "true", "yes"))
    pages = query.order_by(LandingPage.updated_at.desc()).all()
    return jsonify([landing_dict(lp, html=False) for lp in pages])


@bp.get("/landing-pages/<slug>")
@require_token
def get_landing_page(slug):
    lp = LandingPage.query.filter_by(slug=slug).first()
    if lp is None:
        return jsonify(error="landing page not found"), 404
    return jsonify(landing_dict(lp))


@bp.post("/landing-pages")
@require_token
def create_landing_page():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(error="title is required"), 400
    html = data.get("html")
    if not html:
        return jsonify(error="html is required"), 400
    lp = LandingPage(
        title=title,
        html=html,
        published=bool(data.get("published", True)),
    )
    lp.slug = unique_slug(data.get("slug") or title, LandingPage, fallback="lp")
    db.session.add(lp)
    db.session.commit()
    return jsonify(landing_dict(lp)), 201


@bp.patch("/landing-pages/<int:page_id>")
@require_token
def update_landing_page(page_id):
    lp = db.session.get(LandingPage, page_id)
    if lp is None:
        return jsonify(error="landing page not found"), 404
    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify(error="title cannot be empty"), 400
        lp.title = title
    if "html" in data:
        html = data.get("html")
        if not html:
            return jsonify(error="html cannot be empty"), 400
        lp.html = html
    if "published" in data:
        lp.published = bool(data.get("published"))
    if data.get("slug"):
        lp.slug = unique_slug(data["slug"], LandingPage, fallback="lp", current_id=lp.id)
    db.session.commit()
    return jsonify(landing_dict(lp))


@bp.post("/landing-pages/<int:page_id>/publish")
@require_token
def publish_landing_page(page_id):
    lp = db.session.get(LandingPage, page_id)
    if lp is None:
        return jsonify(error="landing page not found"), 404
    lp.published = True
    db.session.commit()
    return jsonify(landing_dict(lp, html=False))


@bp.post("/landing-pages/<int:page_id>/unpublish")
@require_token
def unpublish_landing_page(page_id):
    lp = db.session.get(LandingPage, page_id)
    if lp is None:
        return jsonify(error="landing page not found"), 404
    lp.published = False
    db.session.commit()
    return jsonify(landing_dict(lp, html=False))


@bp.delete("/landing-pages/<int:page_id>")
@require_token
def delete_landing_page(page_id):
    lp = db.session.get(LandingPage, page_id)
    if lp is None:
        return jsonify(error="landing page not found"), 404
    db.session.delete(lp)
    db.session.commit()
    return jsonify(deleted=page_id)
