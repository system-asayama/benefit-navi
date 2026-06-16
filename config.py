import os


def _env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    """環境変数から設定を読み込む。未設定時はローカル開発向けの値を使う。"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # docker-compose では postgresql://app:app@db:5432/benefit_navi が渡される。
    # 未設定時はローカルの SQLite にフォールバックして単体でも動かせるようにする。
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///benefit_navi.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 初回起動時に作成する管理ユーザー
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

    SITE_NAME = os.environ.get("SITE_NAME", "ベネフィットナビ")
    SITE_TAGLINE = os.environ.get(
        "SITE_TAGLINE", "投資・福利厚生・副業の「知って得する」情報をお届け"
    )

    # REST API（MCP 連携用）のアクセストークン。
    # 未設定（空）の場合は API を無効化し、外部からの書き込みを受け付けない。
    API_TOKEN = os.environ.get("API_TOKEN", "")

    # ---- 管理者ログインのセキュリティ設定 ----------------------------------

    # セッション/ログイン用 Cookie の保護。
    # SESSION_COOKIE_SECURE は HTTPS 環境では必ず true にする（本番で有効化）。
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=False)

    # CSRF トークンの有効期限（秒）。None で「セッション有効中はずっと有効」。
    WTF_CSRF_TIME_LIMIT = int(os.environ.get("WTF_CSRF_TIME_LIMIT", "3600"))

    # ログイン総当たり対策（ユーザー名単位）。
    # 規定回数連続で失敗するとロックアウトする。
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))

    # 管理者パスワードの最低文字数（管理画面からの追加・作成時に検証）。
    ADMIN_PASSWORD_MIN_LENGTH = int(os.environ.get("ADMIN_PASSWORD_MIN_LENGTH", "8"))
