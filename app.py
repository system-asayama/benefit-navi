import markdown as md
from flask import Flask
from markupsafe import Markup

from config import Config
from extensions import db, login_manager
from utils import init_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from models import AdminUser

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(AdminUser, int(user_id))

    @app.template_filter("markdown")
    def render_markdown(text):
        html = md.markdown(
            text or "",
            extensions=["extra", "sane_lists", "nl2br", "toc"],
        )
        return Markup(html)

    @app.context_processor
    def inject_site():
        return {
            "site_name": app.config["SITE_NAME"],
            "site_tagline": app.config["SITE_TAGLINE"],
        }

    from views.admin import bp as admin_bp
    from views.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    init_db(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
