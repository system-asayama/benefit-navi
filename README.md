# benefit-navi（ベネフィットナビ）

投資・福利厚生・副業など「知って得する」情報を、カテゴリごとの記事（LP）として
配信する Flask アプリです。記事は管理画面（CMS）から追加・編集できます。

## 構成

- **Flask 3** + **Flask-SQLAlchemy** + **Flask-Login**
- **PostgreSQL**（`docker-compose` で同梱。`DATABASE_URL` 未設定時は SQLite にフォールバック）
- 記事本文は **Markdown / HTML** で記述（私が作成したコンテンツをそのまま貼り付け可能）

```
app.py            アプリ生成（create_app）と gunicorn 用 app
config.py         環境変数ベースの設定
extensions.py     db / login_manager
models.py         Category / Article / AdminUser
utils.py          slug 生成・初期データ投入(seed)
views/public.py   公開ページ（トップ / カテゴリ / 記事）
views/admin.py    管理画面（ログイン / 記事CRUD / カテゴリ管理）
templates/        Jinja2 テンプレート
static/style.css  スタイル
```

## 起動

### Docker Compose（PostgreSQL 同梱）

```bash
docker compose up --build
# http://localhost:8000        公開サイト
# http://localhost:8000/admin  管理画面
```

### ローカル（SQLite）

```bash
pip install -r requirements.txt
python app.py
```

## 管理画面

`/admin/login` からログイン。初期ユーザーは環境変数で設定します（未設定時は
`admin` / `changeme`）。**本番では必ず変更してください。**

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `SECRET_KEY` | `dev-secret-change-me` | セッション署名鍵 |
| `DATABASE_URL` | SQLite | DB 接続文字列 |
| `ADMIN_USERNAME` | `admin` | 初期管理ユーザー名 |
| `ADMIN_PASSWORD` | `changeme` | 初期管理パスワード |
| `SITE_NAME` | ベネフィットナビ | サイト名 |
| `SITE_TAGLINE` | （説明文） | サイトのキャッチコピー |

初回起動時に初期カテゴリ（投資 / 福利厚生 / 副業）とサンプル記事、管理ユーザーが
自動作成されます。
