# benefit-navi（ベネフィットナビ）

投資・福利厚生・副業など「知って得する」情報を、カテゴリごとの記事（LP）として
配信する Flask アプリです。記事は管理画面（CMS）から追加・編集できます。

> Web コンテナは内部で 8000 番を待ち受け、既定ではホストの **8080** 番に公開します
> （`WEB_PORT` で変更可）。

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
# http://localhost:8080        公開サイト（WEB_PORT で変更可）
# http://localhost:8080/admin  管理画面
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

## MCP 連携（Claude から記事を作成する）

CMS への手入力の代わりに、Claude に「投資カテゴリで新NISAの記事を書いて公開して」と
頼むと、MCP 経由で記事が直接登録されます。**サブスク版の Claude に接続すれば追加の
API 課金は不要**です（MCP サーバーは本体の REST API をラップするだけ）。

### 1. アプリ側で API を有効化

`API_TOKEN` を設定して起動します（空だと API は 503 で無効）。

```bash
export API_TOKEN=$(openssl rand -hex 24)
docker compose up --build      # もしくは python app.py
```

REST API（すべて `Authorization: Bearer <API_TOKEN>` が必要）:

| メソッド | パス | 説明 |
| --- | --- | --- |
| GET | `/api/categories` | カテゴリ一覧 |
| POST | `/api/categories` | カテゴリ作成 |
| GET | `/api/articles` | 記事一覧（`?category=`, `?published=`） |
| GET | `/api/articles/<slug>` | 記事取得（本文付き） |
| POST | `/api/articles` | 記事作成 |
| PATCH | `/api/articles/<id>` | 記事の部分更新 |
| POST | `/api/articles/<id>/publish` | 公開 |
| POST | `/api/articles/<id>/unpublish` | 下書きに戻す |
| DELETE | `/api/articles/<id>` | 削除 |
| GET | `/api/landing-pages` | LP一覧（`?published=`、HTML本文なし） |
| GET | `/api/landing-pages/<slug>` | LP取得（HTML付き） |
| POST | `/api/landing-pages` | LP作成（`title`, `html` 必須） |
| PATCH | `/api/landing-pages/<id>` | LPの部分更新 |
| POST | `/api/landing-pages/<id>/publish` | 公開 |
| POST | `/api/landing-pages/<id>/unpublish` | 下書きに戻す |
| DELETE | `/api/landing-pages/<id>` | 削除 |

#### ランディングページ（独自デザインのLP）

記事は固定テンプレートに Markdown を流し込みますが、**ランディングページは渡した
HTML をそのまま `/lp/<slug>` で配信**します（サイト共通のヘッダー/フッターで包まれ
ません）。Claude に「〜のLPを作って」と頼むと、MCP 経由でデザインごと1ページが
追加されます。MCP ツール: `create_landing_page` / `update_landing_page` /
`list_landing_pages` / `get_landing_page` / `publish_landing_page` /
`unpublish_landing_page` / `delete_landing_page`。管理画面の「LP」タブからも
一覧・編集・削除できます。

### 2. MCP サーバーを Claude に接続

```bash
pip install -r requirements-mcp.txt
export BENEFIT_NAVI_API_URL=http://localhost:8000   # 公開先がある場合はそのURL
export BENEFIT_NAVI_API_TOKEN=$API_TOKEN
```

**Claude Code の場合:**

```bash
claude mcp add benefit-navi \
  -e BENEFIT_NAVI_API_URL=http://localhost:8000 \
  -e BENEFIT_NAVI_API_TOKEN=$API_TOKEN \
  -- python /absolute/path/to/mcp_server.py
```

**Claude Desktop の場合**（`claude_desktop_config.json`）:

```json
{
  "mcpServers": {
    "benefit-navi": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_server.py"],
      "env": {
        "BENEFIT_NAVI_API_URL": "http://localhost:8000",
        "BENEFIT_NAVI_API_TOKEN": "ここにAPI_TOKEN"
      }
    }
  }
}
```

接続後は次のツールが使えます: `list_categories` / `create_category` /
`list_articles` / `get_article` / `create_article` / `update_article` /
`publish_article` / `unpublish_article`。
