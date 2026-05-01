"""
Regression tests for /api/apps endpoints.
Covers: CRUD, sessions, messages, and migration (opening_msg column).
"""
from __future__ import annotations

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _app_payload(**kwargs):
    return {
        "name": "测试应用",
        "description": "回归测试用",
        "icon": "🧪",
        "opening_msg": "欢迎！",
        "system_prompt": "你是测试助手",
        "variables": [],
        "tools": ["web_search"],
        "model": "",
        **kwargs,
    }


# ── App CRUD ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_apps_empty(client):
    resp = await client.get("/api/apps")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_create_app_basic(client):
    resp = await client.post("/api/apps", json=_app_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试应用"
    assert data["icon"] == "🧪"
    assert data["opening_msg"] == "欢迎！"
    assert data["tools"] == ["web_search"]
    assert data["is_published"] is False
    assert data["id"].startswith("app_")


@pytest.mark.asyncio
async def test_create_app_opening_msg_persisted(client):
    """Regression: opening_msg column must exist (migration test)."""
    payload = _app_payload(opening_msg="你好，我是你的助手！")
    resp = await client.post("/api/apps", json=payload)
    assert resp.status_code == 200, resp.text
    app_id = resp.json()["id"]

    # Fetch and verify
    get_resp = await client.get(f"/api/apps/{app_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["opening_msg"] == "你好，我是你的助手！"


@pytest.mark.asyncio
async def test_get_app_not_found(client):
    resp = await client.get("/api/apps/nonexistent_id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_apps_returns_created(client):
    await client.post("/api/apps", json=_app_payload(name="App A"))
    await client.post("/api/apps", json=_app_payload(name="App B"))
    resp = await client.get("/api/apps")
    names = [a["name"] for a in resp.json()["items"]]
    assert "App A" in names
    assert "App B" in names


@pytest.mark.asyncio
async def test_update_app(client):
    create = await client.post("/api/apps", json=_app_payload())
    app_id = create.json()["id"]

    resp = await client.put(f"/api/apps/{app_id}", json={
        "name": "更新后名称",
        "system_prompt": "新提示词",
        "tools": ["bash", "python_exec"],
        "is_published": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "更新后名称"
    assert data["system_prompt"] == "新提示词"
    assert set(data["tools"]) == {"bash", "python_exec"}
    assert data["is_published"] is True


@pytest.mark.asyncio
async def test_update_opening_msg(client):
    create = await client.post("/api/apps", json=_app_payload(opening_msg="原欢迎语"))
    app_id = create.json()["id"]

    resp = await client.put(f"/api/apps/{app_id}", json={"opening_msg": "新欢迎语"})
    assert resp.status_code == 200
    assert resp.json()["opening_msg"] == "新欢迎语"


@pytest.mark.asyncio
async def test_delete_app(client):
    create = await client.post("/api/apps", json=_app_payload())
    app_id = create.json()["id"]

    del_resp = await client.delete(f"/api/apps/{app_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True

    get_resp = await client.get(f"/api/apps/{app_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_app_cascades_sessions(client):
    """Deleting an app must also delete its sessions and messages."""
    create = await client.post("/api/apps", json=_app_payload())
    app_id = create.json()["id"]

    sess = await client.post(f"/api/apps/{app_id}/sessions", json={})
    assert sess.status_code == 200

    await client.delete(f"/api/apps/{app_id}")

    # Sessions endpoint should return 404 or empty after app deletion
    # (app_id is gone, no sessions should exist)
    list_resp = await client.get(f"/api/apps/{app_id}/sessions")
    # Either 404 (app gone) or empty list — both acceptable
    assert list_resp.status_code in (200, 404)
    if list_resp.status_code == 200:
        assert list_resp.json()["items"] == []


# ── Variables ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_app_with_variables(client):
    variables = [
        {"key": "language", "label": "目标语言", "type": "text", "required": True, "default": "英文"},
        {"key": "tone", "label": "风格", "type": "select", "required": False, "default": "正式",
         "options": ["正式", "幽默"]},
    ]
    resp = await client.post("/api/apps", json=_app_payload(variables=variables))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["variables"]) == 2
    assert data["variables"][0]["key"] == "language"
    assert data["variables"][1]["options"] == ["正式", "幽默"]


# ── Sessions ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_sessions(client):
    create = await client.post("/api/apps", json=_app_payload())
    app_id = create.json()["id"]

    s1 = await client.post(f"/api/apps/{app_id}/sessions", json={})
    s2 = await client.post(f"/api/apps/{app_id}/sessions", json={})
    assert s1.status_code == 200
    assert s2.status_code == 200
    assert s1.json()["id"] != s2.json()["id"]

    list_resp = await client.get(f"/api/apps/{app_id}/sessions")
    assert list_resp.status_code == 200
    ids = [s["id"] for s in list_resp.json()["items"]]
    assert s1.json()["id"] in ids
    assert s2.json()["id"] in ids


@pytest.mark.asyncio
async def test_get_messages_empty(client):
    create = await client.post("/api/apps", json=_app_payload())
    app_id = create.json()["id"]
    sess = await client.post(f"/api/apps/{app_id}/sessions", json={})
    session_id = sess.json()["id"]

    resp = await client.get(f"/api/apps/{app_id}/sessions/{session_id}/messages")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ── Tools field roundtrip ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tools_empty_list(client):
    resp = await client.post("/api/apps", json=_app_payload(tools=[]))
    assert resp.status_code == 200
    assert resp.json()["tools"] == []


@pytest.mark.asyncio
async def test_tools_multiple(client):
    tools = ["web_search", "python_exec", "bash", "read_file"]
    resp = await client.post("/api/apps", json=_app_payload(tools=tools))
    assert resp.status_code == 200
    assert set(resp.json()["tools"]) == set(tools)
