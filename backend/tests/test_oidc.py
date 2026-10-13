"""OIDC crypto/state/nonce/PKCE validation against a deterministic signed issuer."""
import time
from urllib.parse import parse_qs, urlparse
import httpx
import pytest
from authlib.integrations.starlette_client import OAuth
from authlib.jose import jwt, JsonWebKey
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db import Base, get_db
from app.models import AuthSession, Learner
from app import auth
from app.settings import settings

@pytest.fixture
def issuer(monkeypatch):
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    def database():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=database
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    pem=private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    key=JsonWebKey.import_key(pem,{"kid":"fixture-key"})
    state={"nonce":"", "bad":"", "pkce_checked":False}
    def transport(request):
        if request.url.path=="/.well-known/openid-configuration":
            return httpx.Response(200,json={"issuer":"https://issuer.test","authorization_endpoint":"https://issuer.test/authorize","token_endpoint":"https://issuer.test/token","jwks_uri":"https://issuer.test/jwks","response_types_supported":["code"],"id_token_signing_alg_values_supported":["RS256"],"code_challenge_methods_supported":["S256"]})
        if request.url.path=="/jwks":return httpx.Response(200,json={"keys":[key.as_dict(is_private=False)]})
        if request.url.path=="/token":
            form=parse_qs(request.content.decode())
            state["pkce_checked"]=bool(form.get("code_verifier"))
            now=int(time.time())
            claims={"iss":"https://issuer.test","sub":"synthetic-subject","aud":"fixture-client","exp":now+300,"iat":now,"nonce":state["nonce"],"name":"Synthetic OIDC learner"}
            if state["bad"]=="nonce":claims["nonce"]="wrong"
            if state["bad"]=="aud":claims["aud"]="wrong"
            if state["bad"]=="issuer":claims["iss"]="https://evil.test"
            if state["bad"]=="expiry":claims["exp"]=now-1000
            signed=jwt.encode({"alg":"RS256","kid":"fixture-key"},claims,key).decode()
            if state["bad"]=="signature":signed=signed[:-8]+"AAAAAAAA"
            return httpx.Response(200,json={"access_token":"synthetic-token","token_type":"Bearer","id_token":signed})
        raise AssertionError(str(request.url))
    oauth=OAuth()
    oauth.register("oidc",client_id="fixture-client",client_secret="synthetic-secret",server_metadata_url="https://issuer.test/.well-known/openid-configuration",client_kwargs={"scope":"openid profile","code_challenge_method":"S256","transport":httpx.MockTransport(transport)})
    monkeypatch.setattr(auth,"oauth",oauth)
    monkeypatch.setattr(settings,"oidc_issuer","https://issuer.test")
    monkeypatch.setattr(settings,"oidc_client_id","fixture-client")
    monkeypatch.setattr(settings,"app_mode","live")
    with TestClient(app) as client:yield client,state,factory
    app.dependency_overrides.clear();engine.dispose()

def begin(client,state):
    response=client.get("/api/v1/auth/login",follow_redirects=False)
    assert response.status_code==302,response.text
    query=parse_qs(urlparse(response.headers["location"]).query)
    assert query["code_challenge_method"]==["S256"] and query["code_challenge"]
    state["nonce"]=query["nonce"][0]
    return query["state"][0]

def test_oidc_issues_opaque_revocable_session_with_pkce(issuer):
    client,state,factory=issuer
    nonce_state=begin(client,state)
    response=client.get("/api/v1/auth/callback",params={"code":"synthetic-code","state":nonce_state},follow_redirects=False)
    assert response.status_code==307,response.text
    assert state["pkce_checked"]
    assert "learningos_session" in response.cookies
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert client.get("/api/v1/me").json()["display_name"]=="Synthetic OIDC learner"
    with factory() as db:
        assert db.scalar(select(AuthSession)).token_hash!=response.cookies["learningos_session"]
        assert db.scalar(select(Learner)).oidc_subject=="synthetic-subject"
    csrf=response.cookies["learningos_csrf"]
    assert client.post("/api/v1/auth/logout",headers={"Origin":settings.frontend_url,"X-CSRF-Token":csrf},follow_redirects=False).status_code==303
    assert client.get("/api/v1/me").status_code==401

@pytest.mark.parametrize("bad",["nonce","aud","issuer","expiry","signature","state"])
def test_oidc_rejects_forged_or_invalid_claims(issuer,bad):
    client,state,factory=issuer
    nonce_state=begin(client,state)
    state["bad"]=bad
    response=client.get("/api/v1/auth/callback",params={"code":"synthetic-code","state":"invalid" if bad=="state" else nonce_state},follow_redirects=False)
    assert response.status_code==401,response.text
    assert "learningos_session" not in response.cookies
    with factory() as db:assert db.scalar(select(AuthSession)) is None
