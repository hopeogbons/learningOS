"""Core isolation and immutable selection checks, using real SQLite FK constraints."""
from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db, utcnow
from app.models import *
from app.auth import get_learner, digest
from app.main import app
from app.settings import settings
from app import jobs

@pytest.fixture
def env(monkeypatch):
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    @event.listens_for(engine,"connect")
    def fk(conn,_):conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    uid,foreign=str(uuid4()),str(uuid4())
    with factory() as db:
        db.add_all([Learner(id=uid,display_name="Synthetic learner"),Learner(id=foreign)]);db.flush()
        collection=Collection(learner_id=uid,name="Chemistry")
        other=Collection(learner_id=foreign,name="Private unrelated collection")
        db.add_all([collection,other]);db.flush()
        chunks,materials=[],[]
        for index,count in enumerate((3,2)):
            material=Material(learner_id=uid,collection_id=collection.id,title=f"Chapter {index}",position=index,status="ready")
            db.add(material);db.flush()
            revision=MaterialRevision(learner_id=uid,collection_id=collection.id,material_id=material.id,content_hash=str(index),extracted_text="Synthetic source")
            db.add(revision);db.flush();material.current_revision_id=revision.id;materials.append(material.id)
            for pos in range(count):
                chunk=Chunk(learner_id=uid,material_revision_id=revision.id,title=f"Title {index}-{pos}",position=pos)
                db.add(chunk);db.flush();chunks.append(chunk.id)
        notice=Notification(learner_id=foreign,kind="test",title="Private notice")
        foreign_job=Job(learner_id=foreign,kind="test")
        db.add_all([notice,foreign_job]);db.commit()
        cid,oid,nid,jid=collection.id,other.id,notice.id,foreign_job.id
    def database():
        with factory() as db:
            try:yield db
            except Exception:db.rollback();raise
    def principal(db=Depends(get_db)):return db.get(Learner,uid)
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_learner]=principal
    monkeypatch.setattr(jobs,"SessionLocal",factory)
    with TestClient(app) as client:yield client,factory,uid,foreign,cid,oid,chunks,materials,nid,jid
    app.dependency_overrides.clear()
    engine.dispose()


def test_scope_five_titles_and_immutable_denominator(env):
    c,f,uid,_,cid,_,chunks,mats,*_=env
    response=c.post(f"/api/v1/collections/{cid}/scope",json={"chunk_ids":chunks,"expected_version":1})
    assert response.status_code==201,response.text
    sid=response.json()["scope_revision"]["id"]
    assert response.json()["progress"]["total_in_scope"]==5
    with f() as db:
        db.add(Chunk(learner_id=uid,material_revision_id=db.get(Material,mats[0]).current_revision_id,title="Late",position=3));db.commit()
    assert c.get(f"/api/v1/collections/{cid}/progress").json()["total_in_scope"]==5
    assert c.post(f"/api/v1/collections/{cid}/scope",json={"chunk_ids":chunks[:2],"expected_version":2}).status_code==201
    assert c.get(f"/api/v1/collections/{cid}/progress",params={"scope_revision_id":sid}).json()["total_in_scope"]==5
    assert c.get(f"/api/v1/collections/{cid}/progress").json()["total_in_scope"]==2


def test_scope_conflict_empty_duplicate_old_revision(env):
    c,f,uid,_,cid,_,chunks,mats,*_=env
    path=f"/api/v1/collections/{cid}/scope"
    assert c.post(path,json={"chunk_ids":[],"expected_version":1}).status_code==422
    assert c.post(path,json={"chunk_ids":[chunks[0]]*2,"expected_version":1}).status_code==422
    assert c.post(path,json={"chunk_ids":chunks,"expected_version":1}).status_code==201
    assert c.post(path,json={"chunk_ids":chunks,"expected_version":1}).status_code==409
    with f() as db:
        r=MaterialRevision(learner_id=uid,collection_id=cid,material_id=mats[0],content_hash="new")
        db.add(r);db.flush();db.get(Material,mats[0]).current_revision_id=r.id;db.commit()
    assert c.post(path,json={"chunk_ids":chunks,"expected_version":2}).status_code==404


def test_reorder_persistence_parent_validation_and_conflict(env):
    c,_,_,_,cid,_,chunks,mats,*_=env
    path=f"/api/v1/collections/{cid}/materials/reorder"
    assert c.patch(path,json={"ordered_ids":mats[:1],"expected_version":1}).status_code==422
    payload={"ordered_ids":mats[::-1],"expected_version":1}
    assert c.patch(path,json=payload).status_code==200
    assert c.patch(path,json=payload).status_code==409
    assert [m["id"] for m in c.get(f"/api/v1/collections/{cid}/outline").json()["materials"]]==mats[::-1]
    path=f"/api/v1/collections/{cid}/materials/{mats[0]}/chunks/reorder"
    assert c.patch(path,json={"ordered_ids":chunks[3:],"expected_version":1}).status_code==422
    assert c.patch(path,json={"ordered_ids":[chunks[0]]*3,"expected_version":1}).status_code==422
    assert c.patch(path,json={"ordered_ids":chunks[:3][::-1],"expected_version":1}).status_code==200
    assert [ch["id"] for ch in c.get(f"/api/v1/collections/{cid}/outline").json()["materials"][1]["chunks"]]==chunks[:3][::-1]


def test_foreign_ids_search_and_export_are_private(env):
    c,_,_,_,_,oid,_,_,nid,jid=env
    for path in [f"collections/{oid}",f"collections/{oid}/outline",f"collections/{oid}/materials",f"collections/{oid}/progress",f"collections/{oid}/history",f"collections/{oid}/weak-spots",f"jobs/{jid}"]:
        assert c.get("/api/v1/"+path).status_code==404,path
    assert c.post(f"/api/v1/notifications/{nid}/read").status_code==404
    assert c.get("/api/v1/search",params={"q":"Private"}).json()["items"]==[]
    assert "Private unrelated" not in c.get("/api/v1/me/export").text


def test_ten_locales_speech_variants_do_not_touch_progress(env):
    c,_,_,_,cid,_,chunks,*_=env
    scope=c.post(f"/api/v1/collections/{cid}/scope",json={"chunk_ids":chunks,"expected_version":1}).json()["scope_revision"]
    before=c.get(f"/api/v1/collections/{cid}/progress").json()
    for locale in ["en","zh-Hans","es","ar","pt","fr","ja","ru","de","id"]:
        assert c.patch("/api/v1/me",json={"ui_locale":locale,"study_locale":locale,"speech_locale":"ar-SA","timezone":"Africa/Lagos"}).status_code==200
    assert c.get(f"/api/v1/collections/{cid}/progress").json()==before
    assert c.get(f"/api/v1/collections/{cid}/outline").json()["active_scope"]==scope
    for field,value in [("ui_locale","zh-CN"),("speech_locale","unavailable"),("timezone","not/a/timezone")]:
        assert c.patch("/api/v1/me",json={field:value}).status_code==422
    assert len(c.get("/api/v1/languages").json()["items"])==10


def test_collection_positions_and_drive_consent(env):
    c,*_=env
    first=c.post("/api/v1/collections",json={"name":"New"}).json()
    second=c.post("/api/v1/collections",json={"name":"Second"}).json()
    assert first["position"]==1 and second["position"]==2
    assert first["storage_mode"]=="local" and first["provisioning_state"]=="local-only"
    assert c.post("/api/v1/collections",json={"name":"No consent","storage_mode":"drive"}).status_code==409


def test_jobs_idempotency_outbox_restart(env):
    _,f,uid,*_=env
    with f() as db:
        one=jobs.enqueue(db,uid,"synthetic",{"value":1},"unique")
        two=jobs.enqueue(db,uid,"synthetic",{"value":2},"unique")
        assert one.id==two.id
        jobs.publish_outbox(db,uid,"aggregate",2,"synthetic",{"value":3})
        jobs.publish_outbox(db,uid,"aggregate",2,"synthetic",{"value":4});db.commit()
    jobs.register("synthetic",lambda db,job:{"value":job.payload["value"]})
    for _ in range(3):assert jobs.run_once()
    with f() as db:
        rows=db.scalars(select(Job).where(Job.learner_id==uid)).all()
        assert len(rows)==2 and {row.state for row in rows}=={"succeeded"}
        assert db.scalar(select(OutboxEvent)).processed_at is not None
    assert not jobs.run_once()


def test_expired_lease_recovers_live_lease_untouched(env):
    _,f,uid,*_=env
    jobs.register("synthetic",lambda db,job:{"recovered":True})
    with f() as db:
        expired=Job(learner_id=uid,kind="synthetic",state="running",lease_owner="crashed",lease_until=utcnow()-timedelta(seconds=1),attempts=1)
        alive=Job(learner_id=uid,kind="synthetic",state="running",lease_owner="other",lease_until=utcnow()+timedelta(minutes=1))
        db.add_all([expired,alive]);db.commit();eid,aid=expired.id,alive.id
    for _ in range(2):jobs.run_once()
    with f() as db:
        assert db.get(Job,eid).state=="succeeded" and db.get(Job,eid).attempts==2
        assert db.get(Job,aid).lease_owner=="other"


def test_handler_failure_rolls_back_partial_mutation(env):
    _,f,uid,*_=env
    def failing(db,job):
        db.add(Notification(learner_id=uid,kind="partial",title="Must roll back"))
        raise jobs.NeedsAttention("synthetic_fail")
    jobs.register("failure",failing)
    with f() as db:
        j=jobs.enqueue(db,uid,"failure",{},"failure");db.commit();jid=j.id
    for _ in range(2):jobs.run_once()
    with f() as db:
        assert db.get(Job,jid).state=="needs-attention"
        assert not db.scalar(select(Notification).where(Notification.kind=="partial"))


def test_live_auth_csrf_and_production_no_demo_bypass(env,monkeypatch):
    c,f,uid,*_=env
    app.dependency_overrides.pop(get_learner)
    monkeypatch.setattr(settings,"app_mode","live")
    assert c.get("/api/v1/me").status_code==401
    with f() as db:
        db.add(AuthSession(learner_id=uid,token_hash=digest("opaque"),csrf_hash=digest("csrf"),expires_at=utcnow()+timedelta(minutes=1)));db.commit()
    c.cookies.set("learningos_session","opaque")
    assert c.get("/api/v1/me").status_code==200
    assert c.patch("/api/v1/me",json={"ui_locale":"ar"}).status_code==403
    assert c.patch("/api/v1/me",headers={"X-CSRF-Token":"csrf","Origin":settings.frontend_url},json={"ui_locale":"ar"}).status_code==200
    assert c.patch("/api/v1/me",headers={"X-CSRF-Token":"csrf","Origin":"https://evil.example"},json={"ui_locale":"ar"}).status_code==403
    with f() as db:
        auth=db.scalar(select(AuthSession));auth.expires_at=utcnow()-timedelta(seconds=1);db.commit()
    assert c.get("/api/v1/me").status_code==401
    with f() as db:
        db.get(Learner,uid).is_demo=True
        auth=db.scalar(select(AuthSession));auth.expires_at=utcnow()+timedelta(minutes=1);db.commit()
    monkeypatch.setattr(settings,"app_mode","production")
    assert c.get("/api/v1/me").status_code==401
    with pytest.raises(RuntimeError):settings.validate()


def test_collection_actual_material_count_and_sync_timestamp(env):
    c,f,uid,_,cid,*_=env
    with f() as db:
        row=db.get(Collection,cid);row.last_sync=utcnow();db.commit()
    dto=c.get(f"/api/v1/collections/{cid}").json()
    assert dto["material_count"]==2
    assert dto["last_sync"]==dto["last_sync_at"] and dto["last_sync"].endswith("+00:00")
    with f() as db:
        db.scalar(select(Material).where(Material.collection_id==cid)).archived=True;db.commit()
    assert c.get(f"/api/v1/collections/{cid}").json()["material_count"]==1


def test_live_job_budget_atomic_admission_and_idempotent_replay(env,monkeypatch):
    _,f,uid,*_=env
    monkeypatch.setattr(settings,"app_mode","live")
    with f() as db:
        for i in range(20):jobs.enqueue(db,uid,"synthetic",{},f"budget:{i}")
        db.commit()
    with f() as db:
        replay=jobs.enqueue(db,uid,"synthetic",{},"budget:0")
        assert replay.idempotency_key=="budget:0"
        with pytest.raises(jobs.JobBudgetExceeded):jobs.enqueue(db,uid,"synthetic",{},"budget:21")
    with f() as db:
        for row in db.scalars(select(Job).where(Job.learner_id==uid)):row.state="succeeded"
        db.commit()
    with f() as db:
        for i in range(20,50):
            row=jobs.enqueue(db,uid,"synthetic",{},f"budget:{i}")
            row.state="succeeded";db.flush()
        db.commit()
    with f() as db:
        with pytest.raises(jobs.JobBudgetExceeded):jobs.enqueue(db,uid,"synthetic",{},"budget:51")


def test_delete_stops_pending_jobs_and_erases_owned_data(env):
    c,f,uid,foreign,cid,*_=env
    with f() as db:
        pending=jobs.enqueue(db,uid,"synthetic",{},"pending-delete");db.commit();pid=pending.id
    response=c.request("DELETE","/api/v1/me",json={"confirmation":"DELETE"})
    assert response.status_code==202
    with f() as db:assert db.get(Job,pid).state=="cancelled"
    for _ in range(2):jobs.run_once()
    with f() as db:
        assert not db.scalar(select(Collection).where(Collection.learner_id==uid))
        assert db.scalar(select(Collection).where(Collection.learner_id==foreign))
        learner=db.get(Learner,uid)
        assert learner.display_name=="Deleted learner" and learner.timezone=="UTC"
        job=db.get(Job,response.json()["job_id"])
        assert job.state=="succeeded" and job.result["deleted"] is True


def test_collection_snapshot_queries_do_not_grow_per_row(env):
    c,f,uid,*_=env
    with f() as db:
        db.add_all([Collection(learner_id=uid,name=f"Synthetic {i}",position=i+1) for i in range(30)]);db.commit()
    engine=f.kw['bind']
    statements=[]
    def query(*args):statements.append(args[2])
    event.listen(engine,"before_cursor_execute",query)
    try:
        response=c.get("/api/v1/collections",params={"limit":50})
        assert response.status_code==200 and response.json()["total"]==31
        assert len(statements)<=8,statements
    finally:event.remove(engine,"before_cursor_execute",query)


def test_search_concepts_citations_and_literal_wildcards_are_owned_paged(env):
    c,f,uid,_,cid,_,chunks,mats,*_=env
    with f() as db:
        revision=db.get(Material,mats[0]).current_revision_id
        citation=Citation(learner_id=uid,revision_id=revision,locator_kind="text",locator_json={},excerpt="Synthetic rarefact 20%",excerpt_hash="hash")
        db.add(citation);db.flush()
        db.add(Concept(learner_id=uid,chunk_id=chunks[0],text="Synthetic rarefact concept",citation_ids=[citation.id]));db.commit()
    result=c.get("/api/v1/search",params={"q":"rarefact","limit":1}).json()
    assert result["total"]==2 and len(result["items"])==1 and result["next_cursor"]==1
    page2=c.get("/api/v1/search",params={"q":"rarefact","limit":1,"cursor":1}).json()
    assert {result["items"][0]["type"],page2["items"][0]["type"]}=={"concept","citation"}
    assert c.get("/api/v1/search",params={"q":"20%"}).json()["total"]==1


def test_authoritative_public_response_models_exclude_private_fields(env):
    c,*_=env
    schema=c.get("/openapi.json").json()
    refs={"/api/v1/me":"LearnerDTO","/api/v1/dashboard":"DashboardDTO","/api/v1/collections":"CollectionListDTO","/api/v1/search":"SearchDTO"}
    for route,name in refs.items():
        assert schema["paths"][route]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]==f"#/components/schemas/{name}"
    for name in ("LearnerDTO","CollectionDTO","DashboardDTO","JobDTO","SearchItemDTO"):
        assert not {"expected_answer","question_json_private","encrypted_credentials","token_hash"} & schema["components"]["schemas"][name].get("properties",{}).keys()
    assert schema["paths"]["/api/v1/me"]["patch"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]=="#/components/schemas/ErrorEnvelopeDTO"


def test_outline_revision_queries_do_not_grow_per_material(env):
    c,f,uid,_,cid,*_=env
    with f() as db:
        for i in range(25):
            m=Material(learner_id=uid,collection_id=cid,title=f"Extra {i}",position=i+2)
            db.add(m);db.flush()
            r=MaterialRevision(learner_id=uid,material_id=m.id,collection_id=cid,content_hash=f"extra:{i}")
            db.add(r);db.flush();m.current_revision_id=r.id
        db.commit()
    engine=f.kw['bind'];statements=[]
    def query(*args):statements.append(args[2])
    event.listen(engine,"before_cursor_execute",query)
    try:
        response=c.get(f"/api/v1/collections/{cid}/outline")
        assert response.status_code==200 and len(response.json()["materials"])==27
        assert len(statements)<=8,statements
    finally:event.remove(engine,"before_cursor_execute",query)
