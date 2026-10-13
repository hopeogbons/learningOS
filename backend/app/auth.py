"""OIDC code/PKCE/nonce via Authlib and opaque revocable DB sessions."""
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlparse
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from .db import get_db, utcnow, as_utc
from .models import Learner, AuthSession
from .settings import settings

DEMO_LEARNER_ID = "00000000-0000-4000-8000-000000000001"
router = APIRouter()
oauth = OAuth()
if settings.oidc_issuer and settings.oidc_client_id:
    oauth.register("oidc", client_id=settings.oidc_client_id, client_secret=settings.oidc_client_secret,
                   server_metadata_url=settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration",
                   client_kwargs={"scope": "openid profile", "code_challenge_method": "S256"})

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def get_learner(request: Request, db=Depends(get_db)):
    if settings.app_mode in {"demo", "test"}:
        learner = db.get(Learner, DEMO_LEARNER_ID)
        if not learner:
            learner = Learner(id=DEMO_LEARNER_ID, display_name="Demo Learner", is_demo=True)
            db.add(learner)
            db.commit()
        return learner
    token = request.cookies.get("learningos_session")
    auth = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(token))) if token else None
    if not auth or auth.revoked or as_utc(auth.expires_at) <= utcnow():
        raise HTTPException(401, "authentication_required")
    learner = db.get(Learner, auth.learner_id)
    if not learner or learner.is_demo:
        raise HTTPException(401, "authentication_required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        origin = request.headers.get("Origin")
        allowed = {settings.public_url.rstrip("/"), settings.frontend_url.rstrip("/")}
        if not csrf or not secrets.compare_digest(digest(csrf), auth.csrf_hash) or origin not in allowed:
            raise HTTPException(403, "csrf_invalid")
    return learner

@router.get("/auth/login")
async def login(request: Request):
    if not settings.oidc_issuer or not settings.oidc_client_id:
        raise HTTPException(503, "oidc_unconfigured")
    return await oauth.oidc.authorize_redirect(request, settings.public_url.rstrip("/") + "/api/v1/auth/callback", nonce=secrets.token_urlsafe(32))

@router.get("/auth/callback")
async def callback(request: Request, db=Depends(get_db)):
    if not settings.oidc_issuer or not settings.oidc_client_id:
        raise HTTPException(503, "oidc_unconfigured")
    try:
        token = await oauth.oidc.authorize_access_token(request)
        claims = token.get("userinfo")
        # Authlib verifies state, nonce, signature, audience, time against discovery/JWKS.
        if not claims or claims.get("iss") != settings.oidc_issuer or not claims.get("sub"):
            raise ValueError("invalid_identity")
    except Exception:
        request.session.clear()
        raise HTTPException(401, "oidc_validation_failed") from None
    learner = db.scalar(select(Learner).where(Learner.oidc_subject == claims["sub"], Learner.oidc_issuer == claims["iss"]))
    if not learner:
        learner = Learner(oidc_subject=claims["sub"], oidc_issuer=claims["iss"], display_name=str(claims.get("name", "Learner"))[:120], is_demo=False)
        db.add(learner)
        db.flush()
    opaque, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(AuthSession(learner_id=learner.id, token_hash=digest(opaque), csrf_hash=digest(csrf), expires_at=utcnow() + timedelta(hours=settings.session_hours)))
    db.commit()
    request.session.clear()
    response = RedirectResponse(settings.frontend_url)
    secure = settings.app_mode == "production" or settings.public_url.startswith("https:")
    response.set_cookie("learningos_session", opaque, httponly=True, secure=secure, samesite="lax", max_age=settings.session_hours * 3600, path="/")
    response.set_cookie("learningos_csrf", csrf, httponly=False, secure=secure, samesite="lax", max_age=settings.session_hours * 3600, path="/")
    return response

@router.post("/auth/logout")
def logout(request: Request, learner=Depends(get_learner), db=Depends(get_db)):
    opaque = request.cookies.get("learningos_session")
    if opaque:
        row = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(opaque), AuthSession.learner_id == learner.id))
        if row:
            row.revoked = True
            db.commit()
    response = RedirectResponse(settings.frontend_url, status_code=303)
    response.delete_cookie("learningos_session")
    response.delete_cookie("learningos_csrf")
    return response
