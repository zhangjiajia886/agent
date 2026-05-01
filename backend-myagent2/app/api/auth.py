from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from ..core.auth import create_token, get_current_user, hash_password, verify_password
from ..db.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str
    password: str
    display_name: str = ""

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("用户名至少 2 个字符")
        if len(v) > 32:
            raise ValueError("用户名最多 32 个字符")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少 6 个字符")
        return v


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(body: RegisterBody):
    db = await get_db()
    cur = await db.execute("SELECT id FROM users WHERE username = ?", (body.username,))
    if await cur.fetchone():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    hashed = hash_password(body.password)
    display = body.display_name.strip() or body.username

    await db.execute(
        "INSERT INTO users (id, username, password_hash, display_name) VALUES (?, ?, ?, ?)",
        (user_id, body.username, hashed, display),
    )
    await db.commit()

    token = create_token(user_id, body.username)
    return {
        "token": token,
        "user": {"id": user_id, "username": body.username, "display_name": display},
    }


@router.post("/login")
async def login(body: LoginBody):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, username, password_hash, display_name FROM users WHERE username = ?",
        (body.username,),
    )
    row = await cur.fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_token(row["id"], row["username"])
    return {
        "token": token,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
        },
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    db = await get_db()
    cur = await db.execute(
        "SELECT id, username, display_name, is_admin, created_at FROM users WHERE id = ?",
        (user["sub"],),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return dict(row)
