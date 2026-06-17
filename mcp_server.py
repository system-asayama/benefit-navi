"""ベネフィットナビ MCP サーバー。

Claude（Claude Desktop / claude.ai / Claude Code など）から記事・カテゴリを
作成・編集できるようにする。ベネフィットナビ本体の REST API をラップするだけなので、
サブスク版 Claude に接続すれば追加の API 課金なしで使える。

環境変数:
  BENEFIT_NAVI_API_URL    例: https://your-host  または http://localhost:8000
  BENEFIT_NAVI_API_TOKEN  Flask 側 API_TOKEN と同じ値

実行: python mcp_server.py   （stdio トランスポート）
依存: pip install -r requirements-mcp.txt
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("BENEFIT_NAVI_API_URL", "http://localhost:8000").rstrip("/")
API_TOKEN = os.environ.get("BENEFIT_NAVI_API_TOKEN", "")

mcp = FastMCP("benefit-navi")


def _client():
    return httpx.Client(
        base_url=f"{API_URL}/api",
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=30,
    )


def _result(resp):
    """HTTP レスポンスを Claude に返しやすい形（JSON or エラーメッセージ）にする。"""
    try:
        data = resp.json()
    except Exception:
        data = {"status_code": resp.status_code, "text": resp.text}
    if resp.status_code >= 400:
        return {"ok": False, "status": resp.status_code, "error": data}
    return data


@mcp.tool()
def list_categories() -> list:
    """カテゴリ一覧（id / name / slug / 記事数）を返す。記事作成前のカテゴリ確認に使う。"""
    with _client() as c:
        return _result(c.get("/categories"))


@mcp.tool()
def create_category(
    name: str, description: str = "", slug: str = "", sort_order: int = 0
) -> dict:
    """新しいカテゴリを作成する。slug は空ならname から自動生成される。"""
    with _client() as c:
        return _result(
            c.post(
                "/categories",
                json={
                    "name": name,
                    "description": description,
                    "slug": slug,
                    "sort_order": sort_order,
                },
            )
        )


@mcp.tool()
def list_articles(category: str = "", published: str = "") -> list:
    """記事一覧（本文なし）を返す。category(slug/name) や published("true"/"false") で絞り込める。"""
    params = {}
    if category:
        params["category"] = category
    if published:
        params["published"] = published
    with _client() as c:
        return _result(c.get("/articles", params=params))


@mcp.tool()
def get_article(slug: str) -> dict:
    """slug を指定して記事1件を本文付きで取得する（編集前の確認に使う）。"""
    with _client() as c:
        return _result(c.get(f"/articles/{slug}"))


@mcp.tool()
def create_article(
    title: str,
    category: str,
    body: str,
    summary: str = "",
    slug: str = "",
    published: bool = True,
) -> dict:
    """記事を作成して公開する。

    body は Markdown（HTML 混在可）。category はカテゴリの slug か name。
    まず list_categories で対象カテゴリを確認してから呼ぶこと。
    """
    with _client() as c:
        return _result(
            c.post(
                "/articles",
                json={
                    "title": title,
                    "category": category,
                    "body": body,
                    "summary": summary,
                    "slug": slug,
                    "published": published,
                },
            )
        )


@mcp.tool()
def update_article(
    article_id: int,
    title: str | None = None,
    category: str | None = None,
    body: str | None = None,
    summary: str | None = None,
    slug: str | None = None,
    published: bool | None = None,
) -> dict:
    """既存記事を部分更新する。指定したフィールドだけが上書きされる。"""
    payload = {}
    if title is not None:
        payload["title"] = title
    if category is not None:
        payload["category"] = category
    if body is not None:
        payload["body"] = body
    if summary is not None:
        payload["summary"] = summary
    if slug is not None:
        payload["slug"] = slug
    if published is not None:
        payload["published"] = published
    with _client() as c:
        return _result(c.patch(f"/articles/{article_id}", json=payload))


@mcp.tool()
def publish_article(article_id: int) -> dict:
    """記事を公開状態にする。"""
    with _client() as c:
        return _result(c.post(f"/articles/{article_id}/publish"))


@mcp.tool()
def unpublish_article(article_id: int) -> dict:
    """記事を下書き（非公開）に戻す。"""
    with _client() as c:
        return _result(c.post(f"/articles/{article_id}/unpublish"))


# ---- ランディングページ（独自デザインの LP） --------------------------------
# 記事と違い、定型テンプレートに流し込まず、渡した HTML をそのまま
# /lp/<slug> で配信する。自分でデザインした完全な1ページを追加していく用途。


@mcp.tool()
def list_landing_pages(published: str = "") -> list:
    """ランディングページ一覧（HTML本文なし）を返す。published("true"/"false")で絞り込める。"""
    params = {}
    if published:
        params["published"] = published
    with _client() as c:
        return _result(c.get("/landing-pages", params=params))


@mcp.tool()
def get_landing_page(slug: str) -> dict:
    """slug を指定してランディングページ1件を HTML 付きで取得する（編集前の確認に使う）。"""
    with _client() as c:
        return _result(c.get(f"/landing-pages/{slug}"))


@mcp.tool()
def create_landing_page(
    title: str,
    html: str,
    slug: str = "",
    published: bool = True,
) -> dict:
    """独自デザインのランディングページを作成して公開する。

    html はページ全体の完全な HTML（<!doctype html> から始まる1ページ）を渡す。
    サイト共通のヘッダー/フッターでは包まれず、この HTML がそのまま
    https://<host>/lp/<slug> で表示される。デザインは自由。
    slug は空なら title から自動生成される。
    """
    with _client() as c:
        return _result(
            c.post(
                "/landing-pages",
                json={
                    "title": title,
                    "html": html,
                    "slug": slug,
                    "published": published,
                },
            )
        )


@mcp.tool()
def update_landing_page(
    page_id: int,
    title: str | None = None,
    html: str | None = None,
    slug: str | None = None,
    published: bool | None = None,
) -> dict:
    """既存のランディングページを部分更新する。指定したフィールドだけ上書きされる。"""
    payload = {}
    if title is not None:
        payload["title"] = title
    if html is not None:
        payload["html"] = html
    if slug is not None:
        payload["slug"] = slug
    if published is not None:
        payload["published"] = published
    with _client() as c:
        return _result(c.patch(f"/landing-pages/{page_id}", json=payload))


@mcp.tool()
def publish_landing_page(page_id: int) -> dict:
    """ランディングページを公開状態にする。"""
    with _client() as c:
        return _result(c.post(f"/landing-pages/{page_id}/publish"))


@mcp.tool()
def unpublish_landing_page(page_id: int) -> dict:
    """ランディングページを下書き（非公開）に戻す。"""
    with _client() as c:
        return _result(c.post(f"/landing-pages/{page_id}/unpublish"))


@mcp.tool()
def delete_landing_page(page_id: int) -> dict:
    """ランディングページを削除する。"""
    with _client() as c:
        return _result(c.delete(f"/landing-pages/{page_id}"))

# ─────────────────────────────────────────────────────────────────────
# HTTP MCP 拡張 (github-support-app の自動 PR で追加)
# github-support-app HTTP/OAuth tail v5 (uvicorn-bind)
# スマホ版 Claude (claude.ai) や リモートクライアントから使える MCP に
# するため、stdio と streamable-http の両モードを切り替えられるようにする。
#
# stdio  : python mcp_server.py             (従来通り、Claude Desktop ローカル用)
# http   : python mcp_server.py --http      (リモート用、port 9100)
#
# claude.ai の Custom Connector は OAuth (DCR + PKCE) を要求するので、
# mcp_oauth.py の最小 OAuth プロバイダーを FastMCP の custom_route で
# 直接 mount する。port バインドは uvicorn で明示的に 0.0.0.0:9100。
# ─────────────────────────────────────────────────────────────────────


def _serve_http() -> None:
    """OAuth + streamable-http MCP サーバーを 0.0.0.0:9100 で起動する。

    手順:
      1. mcp_oauth のハンドラを ``mcp.custom_route`` で FastMCP に登録
      2. FastMCP の ASGI app を ``mcp.streamable_http_app()`` で取得
      3. uvicorn で 0.0.0.0:9100 にバインドして起動

    FastMCP の ``mcp.run()`` は古いバージョンで host/port 引数を受理せず、
    デフォルト 127.0.0.1:8000 にバインドしてしまうので、ASGI app を直接
    uvicorn に渡してポートを確実に固定する。
    """
    import os as _os
    import sys as _sys

    bearer = _os.environ.get("MCP_BEARER_TOKEN") or _os.environ.get(
        "BENEFIT_NAVI_API_TOKEN", ""
    )
    if not bearer:
        print("[mcp_http] WARN: MCP_BEARER_TOKEN が空。/mcp は無認証で公開されます。",
              file=_sys.stderr)

    # ── OAuth ハンドラを FastMCP に登録 ──
    try:
        from mcp_oauth import (
            well_known_authorization_server,
            well_known_protected_resource,
            register as oauth_register,
            authorize as oauth_authorize,
            token as oauth_token,
        )
        try:
            mcp.custom_route(
                "/.well-known/oauth-authorization-server", methods=["GET"]
            )(well_known_authorization_server)
            mcp.custom_route(
                "/.well-known/oauth-protected-resource", methods=["GET"]
            )(well_known_protected_resource)
            mcp.custom_route("/oauth/register", methods=["POST"])(oauth_register)
            mcp.custom_route("/oauth/authorize", methods=["GET"])(oauth_authorize)
            mcp.custom_route("/oauth/token", methods=["POST"])(oauth_token)
            print("[mcp_http] OAuth routes 登録完了 (custom_route)",
                  file=_sys.stderr)
        except (AttributeError, TypeError) as e:
            print(f"[mcp_http] custom_route 利用不可 ({e})。OAuth 無しで起動。",
                  file=_sys.stderr)
    except ImportError as e:
        print(f"[mcp_http] mcp_oauth.py import 失敗 ({e})。OAuth 無しで起動。",
              file=_sys.stderr)

    # ── uvicorn で明示的に 0.0.0.0:9100 にバインド ──
    try:
        import uvicorn
        app = mcp.streamable_http_app()
        print("[mcp_http] uvicorn を 0.0.0.0:9100 で起動",
              file=_sys.stderr)
        uvicorn.run(app, host="0.0.0.0", port=9100, log_level="info")
        return
    except (AttributeError, ImportError) as e:
        print(f"[mcp_http] uvicorn 経路失敗 ({e})。FastMCP run に fallback。",
              file=_sys.stderr)

    # ── 最終フォールバック: FastMCP の run (port 指定不可なケース) ──
    try:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = 9100
    except AttributeError:
        pass
    try:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=9100)
    except TypeError:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    import sys as _sys
    if "--http" in _sys.argv:
        _serve_http()
    else:
        mcp.run()
