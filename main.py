
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from pydantic import BaseModel
import sqlite3
from auth import db_session, init, now, hash_pw, check_pw, make_token, read_token


class Register(BaseModel):
    name: str
    email: str
    password: str
    branch: str = "CSE"


class Login(BaseModel):
    email: str
    password: str


class NoteIn(BaseModel):
    subject: str = "General"
    title: str
    content: str
    tags: str = ""


bearer = HTTPBearer(auto_error=False)


def me(cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not cred:
        raise HTTPException(401, "Login first: click Authorize, paste token")
    data = read_token(cred.credentials)
    if not data:
        raise HTTPException(401, "Token bad or expired, login again")
    with db_session() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (data["sub"],)).fetchone()
    if not row:
        raise HTTPException(401, "User deleted")
    return dict(row)


@asynccontextmanager
async def life(app: FastAPI):
    init()
    yield


app = FastAPI(title="StudyVault API", lifespan=life)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "StudyVault"}


@app.post("/api/auth/register", status_code=201)
def register(b: Register):
    if len(b.password) < 4:
        raise HTTPException(400, "Password min 4 chars")
    try:
        with db_session() as c:
            c.execute("INSERT INTO users(name,email,pw,branch) VALUES(?,?,?,?)",
                      (b.name, b.email, hash_pw(b.password, b.email), b.branch))
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Email already used")
    return {"name": b.name, "email": b.email}


@app.post("/api/auth/login")
def login(b: Login):
    with db_session() as c:
        r = c.execute("SELECT * FROM users WHERE email=?", (b.email,)).fetchone()
    if not r or not check_pw(b.password, b.email, r["pw"]):
        raise HTTPException(401, "Wrong email or password")
    return {"access_token": make_token(r["email"]), "token_type": "bearer"}


@app.get("/api/notes")
def notes(q: str = "", subject: str = ""):
    with db_session() as c:
        rows = c.execute(
            "SELECT * FROM notes ORDER BY upvotes DESC, id DESC"
        ).fetchall()
    out = [dict(r) for r in rows]
    if subject:
        out = [x for x in out if x["subject"].lower() == subject.lower()]
    if q:
        ql = q.lower()
        out = [x for x in out if ql in (x["title"] + x["content"] + x["tags"]).lower()]
    return out


@app.post("/api/notes", status_code=201)
def create(n: NoteIn, u: dict = Depends(me)):
    if not n.title.strip() or not n.content.strip():
        raise HTTPException(400, "Title + content required")
    with db_session() as c:
        cur = c.execute(
            "INSERT INTO notes(owner,subject,title,content,tags,upvotes,created) "
            "VALUES(?,?,?,?,?,?,?)",
            (u["email"], n.subject.strip(), n.title.strip(), n.content.strip(),
             n.tags.strip(), 0, now()),
        )
        note_id = cur.lastrowid
    return {"id": note_id, "title": n.title, "subject": n.subject}


@app.post("/api/notes/{nid}/upvote")
def upvote(nid: int, u: dict = Depends(me)):
    try:
        with db_session() as c:
            if not c.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone():
                raise HTTPException(404, "Note not found")
            c.execute("INSERT INTO votes(email,note_id) VALUES(?,?)", (u["email"], nid))
            c.execute("UPDATE notes SET upvotes=upvotes+1 WHERE id=?", (nid,))
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Already upvoted")
    return {"id": nid, "upvoted": True}


@app.delete("/api/notes/{nid}")
def delete(nid: int, u: dict = Depends(me)):
    with db_session() as c:
        r = c.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
        if not r:
            raise HTTPException(404, "Note not found")
        if r["owner"] != u["email"]:
            raise HTTPException(403, "Only owner can delete")
        c.execute("DELETE FROM notes WHERE id=?", (nid,))
        c.execute("DELETE FROM votes WHERE note_id=?", (nid,))
    return {"deleted": nid}


@app.get("/api/stats")
def stats():
    with db_session() as c:
        rows = c.execute("SELECT subject, upvotes FROM notes").fetchall()
    subs = {}
    for r in rows:
        subs[r["subject"]] = subs.get(r["subject"], 0) + 1
    return {"total_notes": len(rows),
            "total_upvotes": sum(r["upvotes"] for r in rows),
            "by_subject": subs}
