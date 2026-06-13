from flask import Blueprint, render_template

from models import Article, Category

bp = Blueprint("public", __name__)


def _nav_categories():
    return Category.query.order_by(Category.sort_order, Category.name).all()


@bp.route("/")
def index():
    categories = _nav_categories()
    latest = (
        Article.query.filter_by(published=True)
        .order_by(Article.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template("index.html", categories=categories, latest=latest)


@bp.route("/category/<slug>")
def category(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    articles = (
        Article.query.filter_by(category_id=cat.id, published=True)
        .order_by(Article.created_at.desc())
        .all()
    )
    return render_template(
        "category.html",
        category=cat,
        articles=articles,
        categories=_nav_categories(),
    )


@bp.route("/article/<slug>")
def article(slug):
    art = Article.query.filter_by(slug=slug, published=True).first_or_404()
    related = (
        Article.query.filter(
            Article.category_id == art.category_id,
            Article.id != art.id,
            Article.published.is_(True),
        )
        .order_by(Article.created_at.desc())
        .limit(4)
        .all()
    )
    return render_template(
        "article.html",
        article=art,
        related=related,
        categories=_nav_categories(),
    )
