from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message = "ログインが必要です。"
# セッション固定攻撃やCookie盗用を検知してログアウトさせる。
login_manager.session_protection = "strong"

# すべての POST/PUT/PATCH/DELETE フォームに CSRF トークンを要求する。
csrf = CSRFProtect()
