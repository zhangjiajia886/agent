#!/usr/bin/env python3
"""
seed_skills.py — 迁移 claude-code bundled skill + 社区优秀 skill 到 myagent2 数据库。

用法:
    cd backend && python -m scripts.seed_skills

特性:
    - 幂等：按 name + source_type 去重，重复运行不会重复插入
    - 分类导入：bundled / community
    - 为 bundled skill 标记 migration_status = degraded（含运行时代码逻辑）
"""
import asyncio
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import init_db, get_db, close_db


def _id():
    return f"skill_{uuid.uuid4().hex[:12]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


_DATA_FILE = Path(__file__).resolve().parent / "seed_skills_data.json"
SKILLS: list[dict] = json.loads(_DATA_FILE.read_text(encoding="utf-8"))


async def main():
    db_path = str(Path(__file__).resolve().parent.parent / "data" / "agent_flow.db")
    await init_db(db_path)
    db = await get_db()

    inserted, skipped = 0, 0
    for sk in SKILLS:
        row = await db.execute(
            "SELECT id FROM skills WHERE name = ? AND source_type = ?",
            (sk["name"], sk.get("source_type", "user")),
        )
        if await row.fetchone():
            skipped += 1
            continue

        sid = _id()
        now = _now()
        ch = _hash(sk.get("content", ""))
        await db.execute(
            """INSERT INTO skills
               (id,name,description,category,content,tags,is_builtin,
                source_type,source_path,source_repo,
                allowed_tools,arguments,argument_hint,when_to_use,
                context_mode,agent,model,
                variables,required_tools,
                migration_status,migration_notes,content_hash,
                created_at,updated_at)
               VALUES (?,?,?,?,?,?,?, ?,?,?, ?,?,?,?, ?,?,?, ?,?, ?,?,?, ?,?)""",
            (sid, sk["name"], sk.get("description",""), sk.get("category","general"),
             sk.get("content",""), json.dumps(sk.get("tags",[])), int(sk.get("is_builtin",False)),
             sk.get("source_type","user"), sk.get("source_path",""), sk.get("source_repo",""),
             json.dumps(sk.get("allowed_tools",[])), json.dumps(sk.get("arguments",[])),
             sk.get("argument_hint",""), sk.get("when_to_use",""),
             sk.get("context_mode",""), sk.get("agent",""), sk.get("model",""),
             json.dumps(sk.get("variables",[])), json.dumps(sk.get("required_tools",[])),
             sk.get("migration_status",""), sk.get("migration_notes",""), ch,
             now, now),
        )
        inserted += 1

    await db.commit()
    await close_db()
    print(f"Done: {inserted} inserted, {skipped} skipped (duplicate)")


if __name__ == "__main__":
    asyncio.run(main())
