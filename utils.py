from slugify import slugify

from extensions import db


def unique_slug(text, model, fallback="item", current_id=None):
    """text からユニークな slug を生成する。

    日本語タイトルは slugify で空になりがちなので allow_unicode を使い、
    それでも空なら fallback を使う。重複時は -2, -3 ... を付与する。
    """
    base = slugify(text, allow_unicode=True) or slugify(fallback) or "item"
    candidate = base
    n = 2
    while True:
        existing = model.query.filter_by(slug=candidate).first()
        if existing is None or existing.id == current_id:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def init_db(app, retries=10, delay=2):
    """テーブル作成と初期データ投入。DB 起動待ちのためリトライする。"""
    import time

    from models import AdminUser, Article, Category

    last_err = None
    for _ in range(retries):
        try:
            with app.app_context():
                db.create_all()
                _seed(app, AdminUser, Article, Category)
            return
        except Exception as e:  # noqa: BLE001 - 起動時の接続待ちを吸収する
            last_err = e
            time.sleep(delay)
    raise last_err


def _seed(app, AdminUser, Article, Category):
    # 管理ユーザー
    if AdminUser.query.count() == 0:
        admin = AdminUser(username=app.config["ADMIN_USERNAME"])
        admin.set_password(app.config["ADMIN_PASSWORD"])
        db.session.add(admin)

    # 初期カテゴリ
    if Category.query.count() == 0:
        defaults = [
            ("投資", "investment", "新NISA・iDeCo・資産形成の基礎から実践まで", 1),
            ("福利厚生", "benefits", "会社員・フリーランスが使える制度と給付金", 2),
            ("副業", "side-business", "始め方・税金・おすすめの稼ぎ方", 3),
        ]
        for name, slug, desc, order in defaults:
            db.session.add(
                Category(name=name, slug=slug, description=desc, sort_order=order)
            )
        db.session.flush()

        # サンプル記事（本文は Markdown）
        inv = Category.query.filter_by(slug="investment").first()
        ben = Category.query.filter_by(slug="benefits").first()
        side = Category.query.filter_by(slug="side-business").first()

        samples = [
            (
                inv,
                "新NISAを最速で理解する3つのポイント",
                "shin-nisa-3points",
                "2024年から始まった新NISA。非課税のしくみを3分で押さえましょう。",
                "## 新NISAとは\n\n2024年から始まった新しい少額投資非課税制度です。\n\n"
                "1. **非課税保有限度額は1,800万円**\n"
                "2. つみたて投資枠（年120万円）と成長投資枠（年240万円）\n"
                "3. 非課税期間は**無期限**\n\n"
                "> まずは少額の積立から始めるのがおすすめです。",
            ),
            (
                ben,
                "知らないと損する給付金・助成金まとめ",
                "kyufukin-matome",
                "申請すればもらえるのに見落としがちな制度をまとめました。",
                "## 代表的な制度\n\n"
                "- 高額療養費制度\n- 傷病手当金\n- 教育訓練給付金\n\n"
                "それぞれ申請期限があるため、早めの確認が大切です。",
            ),
            (
                side,
                "副業の始め方と確定申告の基本",
                "fukugyo-start",
                "副業で年20万円を超えたら確定申告。最初に知っておきたい基本。",
                "## 副業を始める前に\n\n"
                "1. 就業規則で副業が認められているか確認\n"
                "2. 収支を記録する習慣をつける\n"
                "3. **年20万円超**の所得は確定申告が必要\n",
            ),
        ]
        for cat, title, slug, summary, body in samples:
            db.session.add(
                Article(
                    title=title,
                    slug=slug,
                    summary=summary,
                    body=body,
                    category=cat,
                    published=True,
                )
            )

    # サンプルのランディングページ（独自デザインのLP例）を1枚用意する。
    from models import LandingPage

    if LandingPage.query.count() == 0:
        from pathlib import Path

        sample = Path(__file__).with_name("samples") / "sample_lp.html"
        try:
            html = sample.read_text(encoding="utf-8")
        except OSError:
            html = ""
        if html:
            db.session.add(
                LandingPage(
                    title="新NISAスタートガイド",
                    slug="shin-nisa-start",
                    html=html,
                    published=True,
                )
            )

    db.session.commit()
