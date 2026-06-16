import os


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
