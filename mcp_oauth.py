# -*- coding: utf-8 -*-
"""Minimal OAuth 2.0 + Dynamic Client Registration for the MCP HTTP server.

claude.ai (および MCP 2025-03-26 仕様準拠の他のリモート MCP クライアント) は
Custom Connector の認証として OAuth (DCR + PKCE) を要求する。本モジュールは
そのために必要な最小限のエンドポイントを Starlette ルートで提供する。

提供エンドポイント:
  GET  /.well-known/oauth-authorization-server  (RFC 8414 — AS メタデータ)
  GET  /.well-known/oauth-protected-resource    (リソースサーバーメタデータ)
  POST /oauth/register                          (RFC 7591 — DCR)
  GET  /oauth/authorize                         (auto-approve、UI 無し)
  POST /oauth/token                             (アクセストークン発行)

セキュリティモデル:
  - DCR は全部受け入れ (誰でも client_id を取得できる)
  - authorize は UI 無しで即承認 (ユーザー同意ステップ無し)
  - 発行されるアクセストークンは MCP_BEARER_TOKEN 環境変数の値そのもの
    (= 単一の共有秘密。再生成すると全クライアントが invalidate される)

→ 「URL を知ってる人 = 使える」モデル。VPN/nginx Basic 認証等の外側保護を
推奨。本番の機密データを扱う場合は本物の OAuth プロバイダー (Auth0/Clerk 等)
に置き換えること。
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

# In-memory state (プロセス再起動でリセット)
_AUTH_CODES: dict = {}   # code -> {client_id, redirect_uri, code_challenge, expires}
_CLIENTS: dict = {}      # client_id -> {client_secret, redirect_uris}


def _bearer_token() -> str:
    """全クライアント共通のアクセストークン (環境変数経由)。"""
    return (os.environ.get("MCP_BEARER_TOKEN")
            or os.environ.get("BENEFIT_NAVI_API_TOKEN")
            or "")


def _public_base_url(request: Request) -> str:
    """外部 URL (例: https://dev.example.com/mcp) を取得する。

    優先順位:
      1. MCP_PUBLIC_URL 環境変数 (deploy 時に設定)
      2. X-Forwarded-Proto / X-Forwarded-Host (nginx 経由)
      3. request.url から推測
    """
    env_url = os.environ.get("MCP_PUBLIC_URL", "").rstrip("/")
    if env_url:
        return env_url
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (request.headers.get("x-forwarded-host")
             or request.headers.get("host")
             or request.url.netloc)
    # nginx 経由なら /mcp サブパスでマウントされてる想定
    return f"{proto}://{host}/mcp"


async def well_known_authorization_server(request: Request) -> JSONResponse:
    base = _public_base_url(request)
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_post", "client_secret_basic", "none",
        ],
    })


async def well_known_protected_resource(request: Request) -> JSONResponse:
    base = _public_base_url(request)
    return JSONResponse({
        "resource": base,
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    })


async def register(request: Request) -> JSONResponse:
    """RFC 7591 Dynamic Client Registration. 任意のクライアントを受理。"""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    client_id = secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)
    redirect_uris = body.get("redirect_uris") or []
    _CLIENTS[client_id] = {
        "secret": client_secret,
        "redirect_uris": redirect_uris,
    }
    return JSONResponse({
        "client_id": client_id,
        "client_secret": client_secret,
        "client_id_issued_at": int(time.time()),
        "client_secret_expires_at": 0,
        "redirect_uris": redirect_uris,
        "grant_types": body.get("grant_types") or [
            "authorization_code", "refresh_token",
        ],
        "response_types": body.get("response_types") or ["code"],
        "token_endpoint_auth_method": (
            body.get("token_endpoint_auth_method") or "client_secret_post"
        ),
    }, status_code=201)


async def authorize(request: Request):
    """Auto-approve: 同意 UI 無し、即 redirect_uri に code を渡して戻す。"""
    params = request.query_params
    redirect_uri = params.get("redirect_uri", "")
    state = params.get("state", "")
    code_challenge = params.get("code_challenge", "")
    code_challenge_method = params.get("code_challenge_method", "")
    client_id = params.get("client_id", "")
    if not redirect_uri:
        return JSONResponse(
            {"error": "invalid_request",
             "error_description": "missing redirect_uri"},
            status_code=400,
        )
    code = secrets.token_urlsafe(32)
    _AUTH_CODES[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "expires": time.time() + 600,  # 10 分
    }
    q = {"code": code}
    if state:
        q["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{sep}{urlencode(q)}",
        status_code=302,
    )


async def token(request: Request) -> JSONResponse:
    """アクセストークン発行。実体は MCP_BEARER_TOKEN を返すだけ。"""
    form = await request.form()
    grant_type = form.get("grant_type")
    bearer = _bearer_token()
    if not bearer:
        return JSONResponse(
            {"error": "server_error",
             "error_description":
                "MCP_BEARER_TOKEN env var is not set. "
                "Run github-support-app's MCP 接続情報 to generate one."},
            status_code=500,
        )
    if grant_type == "authorization_code":
        code = form.get("code", "")
        code_verifier = form.get("code_verifier", "")
        data = _AUTH_CODES.pop(code, None)
        if not data:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if data["expires"] < time.time():
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        # PKCE (RFC 7636)
        cc = data.get("code_challenge", "")
        if cc:
            method = data.get("code_challenge_method", "plain") or "plain"
            if method == "S256":
                hashed = hashlib.sha256(code_verifier.encode()).digest()
                check = base64.urlsafe_b64encode(hashed).rstrip(b"=").decode()
            else:
                check = code_verifier
            if check != cc:
                return JSONResponse(
                    {"error": "invalid_grant",
                     "error_description": "PKCE verification failed"},
                    status_code=400,
                )
    elif grant_type == "refresh_token":
        # 簡略化: refresh_token と access_token は同じ値、有効期限なし
        pass
    else:
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    return JSONResponse({
        "access_token": bearer,
        "token_type": "Bearer",
        "expires_in": 86400,
        "refresh_token": bearer,
    })


def is_valid_token(value: str) -> bool:
    """Bearer トークンを検証。MCP_BEARER_TOKEN と一致なら OK。"""
    bearer = _bearer_token()
    if not bearer:
        # 環境変数未設定なら認証無効 (= 全許可) フォールバック
        return True
    return value == bearer


def get_oauth_routes():
    """Starlette Route のリストを返す。mcp_server.py から呼び出す。"""
    from starlette.routing import Route
    return [
        Route("/.well-known/oauth-authorization-server",
              well_known_authorization_server, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource",
              well_known_protected_resource, methods=["GET"]),
        Route("/oauth/register", register, methods=["POST"]),
        Route("/oauth/authorize", authorize, methods=["GET"]),
        Route("/oauth/token", token, methods=["POST"]),
    ]
