"""
Unified database layer.

SQLite backend  (DB_TYPE=sqlite, default): uses aiosqlite.
MySQL  backend  (DB_TYPE=mysql):           uses aiomysql with autocommit pool.

Both expose the same cursor API so upper-layer code needs zero changes.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Sequence

import aiosqlite

logger = logging.getLogger(__name__)

_db: Any = None          # aiosqlite.Connection  |  _MySQLDB
_db_type: str = "sqlite"


# ─── MySQL SQL-dialect helpers ────────────────────────────────────────────────

_PRAGMA_TABLE_RE = re.compile(
    r'^\s*PRAGMA\s+table_info\((\w+)\)\s*$', re.IGNORECASE
)


_COALESCE_SUBQUERY_RE = re.compile(
    r'\(SELECT\s+(\w+)\s+FROM\s+(\w+)\s+WHERE\s+([^()]+?)\)',
    re.IGNORECASE,
)


def _wrap_coalesce_subqueries(sql: str) -> str:
    """MySQL error 1093 workaround: wrap SELECT subqueries in a derived table
    so MySQL allows them inside INSERT/REPLACE targeting the same table."""
    def _wrap(m: re.Match) -> str:
        col, tbl, cond = m.group(1), m.group(2), m.group(3)
        return f"(SELECT _t.{col} FROM (SELECT {col} FROM {tbl} WHERE {cond}) AS _t)"
    return _COALESCE_SUBQUERY_RE.sub(_wrap, sql)


def _to_mysql_sql(sql: str) -> str:
    """Minimal SQLite → MySQL dialect conversion."""
    sql = re.sub(r'\bINSERT OR REPLACE INTO\b', 'REPLACE INTO', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bINSERT OR IGNORE INTO\b',  'INSERT IGNORE INTO', sql, flags=re.IGNORECASE)
    sql = _wrap_coalesce_subqueries(sql)
    sql = sql.replace('?', '%s')
    return sql


# ─── Eager cursor (MySQL) ─────────────────────────────────────────────────────

class _EagerCursor:
    """In-memory cursor returned by _MySQLDB.execute(); mimics aiosqlite.Cursor."""
    __slots__ = ("_rows", "rowcount", "lastrowid")

    def __init__(self, rows: list, rowcount: int, lastrowid: Any):
        self._rows = rows
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    async def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list:
        return list(self._rows)

    async def fetchmany(self, size: int = 1) -> list:
        return self._rows[:size]


# ─── MySQL DB wrapper ─────────────────────────────────────────────────────────

class _MySQLDB:
    """
    Wraps aiomysql pool to expose the same interface as aiosqlite.Connection.
    Pool is created with autocommit=True so each statement is immediately durable.
    commit() is kept as a no-op for API compatibility.
    """

    def __init__(self, pool: Any):
        self._pool = pool

    async def execute(self, sql: str, params: Sequence = ()) -> _EagerCursor:
        import aiomysql  # type: ignore

        # PRAGMA table_info → INFORMATION_SCHEMA query
        m = _PRAGMA_TABLE_RE.match(sql.strip())
        if m:
            real_sql = (
                "SELECT COLUMN_NAME AS name "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s"
            )
            params = (m.group(1),)
        else:
            real_sql = _to_mysql_sql(sql)

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(real_sql, params or ())
                rows = await cur.fetchall()
                rc  = cur.rowcount
                lid = cur.lastrowid
        return _EagerCursor(rows, rc, lid)

    async def executemany(self, sql: str, params_seq: Sequence) -> None:
        real_sql = _to_mysql_sql(sql)
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(real_sql, params_seq)

    async def executescript(self, sql: str) -> None:
        """Run multiple ; -separated DDL/DML statements (schema init)."""
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                for stmt in statements:
                    try:
                        await cur.execute(stmt)
                    except Exception as e:
                        logger.debug("MySQL schema stmt skipped (%s): %.120s", e, stmt)

    async def commit(self) -> None:
        pass  # autocommit=True; kept for interface compatibility

    async def close(self) -> None:
        self._pool.close()
        await self._pool.wait_closed()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    definition JSON NOT NULL,
    status TEXT DEFAULT 'draft',
    tags JSON DEFAULT '[]',
    version INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_versions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT REFERENCES workflows(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    definition JSON NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT REFERENCES workflows(id) ON DELETE SET NULL,
    workflow_name TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    inputs JSON DEFAULT '{}',
    outputs JSON DEFAULT '{}',
    node_statuses JSON DEFAULT '{}',
    logs JSON DEFAULT '[]',
    error TEXT DEFAULT '',
    started_at DATETIME,
    finished_at DATETIME,
    total_tokens INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trace_spans (
    id TEXT PRIMARY KEY,
    execution_id TEXT REFERENCES executions(id) ON DELETE CASCADE,
    parent_span_id TEXT,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    tool_name TEXT,
    tool_duration_ms INTEGER DEFAULT 0,
    result_preview TEXT DEFAULT '',
    error TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    definition JSON NOT NULL,
    tags JSON DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'general',
    content TEXT NOT NULL DEFAULT '',
    tags JSON DEFAULT '[]',
    is_builtin INTEGER DEFAULT 0,
    source_type TEXT DEFAULT 'user',
    source_path TEXT DEFAULT '',
    source_repo TEXT DEFAULT '',
    allowed_tools JSON DEFAULT '[]',
    arguments JSON DEFAULT '[]',
    argument_hint TEXT DEFAULT '',
    when_to_use TEXT DEFAULT '',
    context_mode TEXT DEFAULT '',
    agent TEXT DEFAULT '',
    model TEXT DEFAULT '',
    variables JSON DEFAULT '[]',
    required_tools JSON DEFAULT '[]',
    migration_status TEXT DEFAULT '',
    migration_notes TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skill_invocations (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    session_id TEXT DEFAULT '',
    execution_mode TEXT DEFAULT '',
    args_text TEXT DEFAULT '',
    status TEXT DEFAULT 'success',
    duration_ms INTEGER DEFAULT 0,
    result_preview TEXT DEFAULT '',
    invoked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    type TEXT DEFAULT 'system',
    content TEXT NOT NULL DEFAULT '',
    variables JSON DEFAULT '[]',
    tags JSON DEFAULT '[]',
    is_builtin INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'custom',
    type TEXT DEFAULT 'builtin',
    input_schema JSON DEFAULT '{}',
    config JSON DEFAULT '{}',
    is_enabled INTEGER DEFAULT 1,
    risk_level TEXT DEFAULT 'low',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    command TEXT NOT NULL,
    args JSON DEFAULT '[]',
    env JSON DEFAULT '{}',
    auto_start INTEGER DEFAULT 0,
    status TEXT DEFAULT 'disconnected',
    tools_count INTEGER DEFAULT 0,
    tools JSON DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_configs (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    api_base TEXT DEFAULT '',
    api_key_ref TEXT DEFAULT '',
    is_default INTEGER DEFAULT 0,
    max_tokens INTEGER DEFAULT 4096,
    config JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS secrets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    encrypted_value BLOB NOT NULL,
    description TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    policy TEXT DEFAULT 'always_ask',
    conditions JSON DEFAULT '{}',
    description TEXT DEFAULT '',
    priority INTEGER DEFAULT 0,
    is_enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    type TEXT DEFAULT 'file',
    config JSON DEFAULT '{}',
    doc_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT '',
    model TEXT DEFAULT '',
    system_prompt TEXT DEFAULT '',
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT DEFAULT '',
    tool_calls JSON,
    tool_call_id TEXT,
    name TEXT DEFAULT '',
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS apps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    icon TEXT DEFAULT '🤖',
    opening_msg TEXT DEFAULT '',
    system_prompt TEXT DEFAULT '',
    variables JSON DEFAULT '[]',
    tools JSON DEFAULT '[]',
    model TEXT DEFAULT '',
    is_published INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_sessions (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    title TEXT DEFAULT '新对话',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES app_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT DEFAULT '',
    tool_calls JSON,
    metadata JSON DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_usages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    duration_ms INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    is_admin INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


MYSQL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workflows (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description LONGTEXT,
    definition LONGTEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'draft',
    tags LONGTEXT,
    version INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS workflow_versions (
    id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64),
    version INT NOT NULL,
    definition LONGTEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS executions (
    id VARCHAR(64) PRIMARY KEY,
    workflow_id VARCHAR(64),
    workflow_name VARCHAR(255) DEFAULT '',
    status VARCHAR(32) DEFAULT 'pending',
    inputs LONGTEXT,
    outputs LONGTEXT,
    node_statuses LONGTEXT,
    logs LONGTEXT,
    error LONGTEXT,
    started_at DATETIME,
    finished_at DATETIME,
    total_tokens INT DEFAULT 0,
    total_cost DOUBLE DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS trace_spans (
    id VARCHAR(64) PRIMARY KEY,
    execution_id VARCHAR(64),
    parent_span_id VARCHAR(64),
    node_id VARCHAR(64) NOT NULL,
    node_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) DEFAULT 'running',
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    model VARCHAR(128),
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    tool_name VARCHAR(128),
    tool_duration_ms INT DEFAULT 0,
    result_preview LONGTEXT,
    error LONGTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS templates (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description LONGTEXT,
    category VARCHAR(64) DEFAULT 'general',
    definition LONGTEXT NOT NULL,
    tags LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS skills (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description LONGTEXT,
    category VARCHAR(64) DEFAULT 'general',
    content LONGTEXT NOT NULL,
    tags LONGTEXT,
    is_builtin TINYINT DEFAULT 0,
    source_type VARCHAR(32) DEFAULT 'user',
    source_path VARCHAR(512) DEFAULT '',
    source_repo VARCHAR(512) DEFAULT '',
    allowed_tools LONGTEXT,
    arguments LONGTEXT,
    argument_hint LONGTEXT,
    when_to_use LONGTEXT,
    context_mode VARCHAR(64) DEFAULT '',
    agent VARCHAR(128) DEFAULT '',
    model VARCHAR(128) DEFAULT '',
    variables LONGTEXT,
    required_tools LONGTEXT,
    migration_status VARCHAR(64) DEFAULT '',
    migration_notes LONGTEXT,
    content_hash VARCHAR(64) DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS skill_invocations (
    id VARCHAR(64) PRIMARY KEY,
    skill_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) DEFAULT '',
    execution_mode VARCHAR(32) DEFAULT '',
    args_text LONGTEXT,
    status VARCHAR(32) DEFAULT 'success',
    duration_ms INT DEFAULT 0,
    result_preview LONGTEXT,
    invoked_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS prompts (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description LONGTEXT,
    type VARCHAR(32) DEFAULT 'system',
    content LONGTEXT NOT NULL,
    variables LONGTEXT,
    tags LONGTEXT,
    is_builtin TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tools (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description LONGTEXT,
    category VARCHAR(64) DEFAULT 'custom',
    type VARCHAR(32) DEFAULT 'builtin',
    input_schema LONGTEXT,
    config LONGTEXT,
    is_enabled TINYINT DEFAULT 1,
    risk_level VARCHAR(16) DEFAULT 'low',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_tools_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mcp_servers (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    command VARCHAR(512) NOT NULL,
    args LONGTEXT,
    env LONGTEXT,
    auto_start TINYINT DEFAULT 0,
    status VARCHAR(32) DEFAULT 'disconnected',
    tools_count INT DEFAULT 0,
    tools LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_mcp_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS model_configs (
    id VARCHAR(64) PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    api_base VARCHAR(512) DEFAULT '',
    api_key_ref LONGTEXT DEFAULT '',
    is_default TINYINT DEFAULT 0,
    max_tokens INT DEFAULT 4096,
    config LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS secrets (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    encrypted_value LONGBLOB NOT NULL,
    description LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_secrets_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS permissions (
    id VARCHAR(64) PRIMARY KEY,
    tool_name VARCHAR(128) NOT NULL,
    policy VARCHAR(32) DEFAULT 'always_ask',
    conditions LONGTEXT,
    description LONGTEXT,
    priority INT DEFAULT 0,
    is_enabled TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description LONGTEXT,
    type VARCHAR(32) DEFAULT 'file',
    config LONGTEXT,
    doc_count INT DEFAULT 0,
    status VARCHAR(32) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(128) PRIMARY KEY,
    value LONGTEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(512) DEFAULT '',
    model VARCHAR(128) DEFAULT '',
    system_prompt LONGTEXT,
    metadata LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS chat_messages (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    content LONGTEXT,
    tool_calls LONGTEXT,
    tool_call_id VARCHAR(128),
    name VARCHAR(128) DEFAULT '',
    metadata LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS apps (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description LONGTEXT,
    icon VARCHAR(16) DEFAULT '🤖',
    opening_msg LONGTEXT,
    system_prompt LONGTEXT,
    variables LONGTEXT,
    tools LONGTEXT,
    model VARCHAR(128) DEFAULT '',
    model_params LONGTEXT,
    is_published TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS app_sessions (
    id VARCHAR(64) PRIMARY KEY,
    app_id VARCHAR(64) NOT NULL,
    title VARCHAR(512) DEFAULT '新对话',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS app_messages (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    content LONGTEXT,
    tool_calls LONGTEXT,
    metadata LONGTEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tool_usages (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tool_name VARCHAR(128) NOT NULL,
    duration_ms INT DEFAULT 0,
    success TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(128) NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    display_name VARCHAR(255) DEFAULT '',
    is_admin TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS memories (
  id            VARCHAR(64) PRIMARY KEY,
  title         VARCHAR(512) NOT NULL,
  content       LONGTEXT NOT NULL,
  type          VARCHAR(32) DEFAULT 'fact',
  tags          VARCHAR(1024),
  corpus_name   VARCHAR(256),
  scope         VARCHAR(32) DEFAULT 'global',
  scope_id      VARCHAR(64),
  milvus_id     VARCHAR(64),
  is_active     TINYINT DEFAULT 1,
  version       INT DEFAULT 1,
  prev_id       VARCHAR(64) NULL,
  created_by    VARCHAR(64),
  source_session_id VARCHAR(64),
  source_message_id VARCHAR(64),
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_scope       (scope, scope_id),
  INDEX idx_corpus      (corpus_name),
  INDEX idx_type        (type, is_active),
  INDEX idx_user_active (created_by, is_active),
  INDEX idx_prev_id     (prev_id),
  FULLTEXT INDEX ft_content (title, content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tasks (
  id            VARCHAR(64) PRIMARY KEY,
  parent_id     VARCHAR(64) NULL,
  root_id       VARCHAR(64) NULL,
  depth         TINYINT DEFAULT 0,
  order_index   INT DEFAULT 0,
  title         VARCHAR(1024) NOT NULL,
  description   TEXT,
  status        VARCHAR(32) DEFAULT 'pending',
  priority      VARCHAR(16) DEFAULT 'medium',
  result        TEXT,
  evidence_tool_call_id VARCHAR(128) NULL,
  session_id    VARCHAR(64),
  session_type  VARCHAR(32),
  execution_id  VARCHAR(64),
  agent_name    VARCHAR(128),
  tool_hint     VARCHAR(256),
  due_at        DATETIME,
  started_at    DATETIME,
  finished_at   DATETIME,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_parent_id (parent_id),
  INDEX idx_root_id   (root_id),
  INDEX idx_session   (session_id, session_type),
  INDEX idx_execution (execution_id),
  INDEX idx_status    (status, priority),
  CONSTRAINT fk_tasks_parent FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS tool_call_logs (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id    VARCHAR(64) NOT NULL,
  session_type  VARCHAR(32) DEFAULT 'chat',
  message_id    VARCHAR(64),
  execution_id  VARCHAR(64),
  tool_call_id  VARCHAR(128) NOT NULL,
  round_num     TINYINT DEFAULT 0,
  tool_name     VARCHAR(128) NOT NULL,
  arguments     LONGTEXT NOT NULL,
  result        LONGTEXT,
  result_preview VARCHAR(512),
  result_size   INT DEFAULT 0,
  result_truncated TINYINT DEFAULT 0,
  status        VARCHAR(32) DEFAULT 'success',
  error         TEXT,
  was_confirmed TINYINT DEFAULT 1,
  duration_ms   INT DEFAULT 0,
  started_at    DATETIME,
  finished_at   DATETIME,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_session      (session_id, session_type),
  INDEX idx_message_id   (message_id),
  INDEX idx_execution_id (execution_id),
  INDEX idx_tool_name    (tool_name, created_at),
  INDEX idx_tool_call_id (tool_call_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS approval_requests (
  id            VARCHAR(64) PRIMARY KEY,
  session_id    VARCHAR(64) NOT NULL,
  session_type  VARCHAR(32) DEFAULT 'chat',
  execution_id  VARCHAR(64),
  tool_call_id  VARCHAR(128) NOT NULL,
  tool_name     VARCHAR(128) NOT NULL,
  arguments     LONGTEXT NOT NULL,
  preview       TEXT,
  risk_level    VARCHAR(16) DEFAULT 'medium',
  status        VARCHAR(32) DEFAULT 'pending',
  decided_by    VARCHAR(64),
  decision_note TEXT,
  decided_at    DATETIME,
  expires_at    DATETIME,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_session        (session_id, status),
  INDEX idx_tool_call_id   (tool_call_id),
  INDEX idx_status_expires (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS conversation_summaries (
  id              VARCHAR(64) PRIMARY KEY,
  session_id      VARCHAR(64) NOT NULL,
  session_type    VARCHAR(32) DEFAULT 'chat',
  summary         LONGTEXT NOT NULL,
  key_facts       LONGTEXT,
  active_tasks    LONGTEXT,
  from_message_id VARCHAR(64),
  to_message_id   VARCHAR(64),
  message_count   INT DEFAULT 0,
  token_count     INT DEFAULT 0,
  compressed_tokens INT DEFAULT 0,
  is_current      TINYINT DEFAULT 1,
  milvus_id       VARCHAR(64),
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_session         (session_id, session_type),
  INDEX idx_created         (session_id, created_at),
  INDEX idx_session_current (session_id, is_current)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS documents (
  id            VARCHAR(64) PRIMARY KEY,
  kb_id         VARCHAR(64) NOT NULL,
  name          VARCHAR(512) NOT NULL,
  source_type   VARCHAR(32) DEFAULT 'file',
  source_url    VARCHAR(2048),
  file_path     VARCHAR(2048),
  file_size     BIGINT DEFAULT 0,
  mime_type     VARCHAR(128),
  checksum      VARCHAR(64),
  status        VARCHAR(32) DEFAULT 'pending',
  chunk_count   INT DEFAULT 0,
  token_count   INT DEFAULT 0,
  error         TEXT,
  meta          LONGTEXT,
  created_by    VARCHAR(64),
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_kb_id     (kb_id),
  INDEX idx_kb_status (kb_id, status),
  INDEX idx_checksum  (checksum),
  CONSTRAINT fk_docs_kb FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS document_chunks (
  id            VARCHAR(64) PRIMARY KEY,
  document_id   VARCHAR(64) NOT NULL,
  kb_id         VARCHAR(64) NOT NULL,
  chunk_index   INT NOT NULL,
  content       LONGTEXT NOT NULL,
  token_count   INT DEFAULT 0,
  char_count    INT DEFAULT 0,
  page_no       INT,
  heading       VARCHAR(512),
  start_char    INT,
  end_char      INT,
  milvus_id     VARCHAR(64),
  embedding_model VARCHAR(128),
  embedded_at   DATETIME,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_doc_id    (document_id),
  INDEX idx_kb_id     (kb_id),
  INDEX idx_milvus_id (milvus_id),
  INDEX idx_doc_chunk (document_id, chunk_index),
  CONSTRAINT fk_chunks_doc FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS rag_citations (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  message_id    VARCHAR(64) NOT NULL,
  session_type  VARCHAR(32) DEFAULT 'chat',
  chunk_id      VARCHAR(64) NOT NULL,
  document_id   VARCHAR(64) NOT NULL,
  kb_id         VARCHAR(64) NOT NULL,
  document_name VARCHAR(512),
  chunk_preview VARCHAR(512),
  page_no       INT,
  score         FLOAT,
  `rank`        TINYINT,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_message_id (message_id),
  INDEX idx_chunk_id   (chunk_id),
  INDEX idx_doc_id     (document_id),
  INDEX idx_kb_id      (kb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS async_tasks (
  id            VARCHAR(64) PRIMARY KEY,
  type          VARCHAR(64) NOT NULL,
  status        VARCHAR(32) DEFAULT 'pending',
  priority      TINYINT DEFAULT 5,
  payload       LONGTEXT NOT NULL,
  result        LONGTEXT,
  error         TEXT,
  progress      TINYINT DEFAULT 0,
  ref_id        VARCHAR(64),
  ref_type      VARCHAR(32),
  created_by    VARCHAR(64),
  worker_id     VARCHAR(128),
  attempts      TINYINT DEFAULT 0,
  max_attempts  TINYINT DEFAULT 3,
  scheduled_at  DATETIME,
  started_at    DATETIME,
  finished_at   DATETIME,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_status_priority (status, priority, scheduled_at),
  INDEX idx_type_status     (type, status),
  INDEX idx_ref             (ref_type, ref_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS message_feedbacks (
  id            VARCHAR(64) PRIMARY KEY,
  message_id    VARCHAR(64) NOT NULL,
  session_type  VARCHAR(32) NOT NULL,
  rating        TINYINT NOT NULL,
  comment       TEXT,
  correction    LONGTEXT,
  tags          VARCHAR(512),
  user_id       VARCHAR(64),
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_message_id (message_id),
  INDEX idx_rating     (rating, created_at),
  INDEX idx_user_id    (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS app_tool_bindings (
  app_id      VARCHAR(64) NOT NULL,
  tool_name   VARCHAR(128) NOT NULL,
  sort_order  INT DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (app_id, tool_name),
  INDEX idx_tool_name (tool_name),
  CONSTRAINT fk_atb_app FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS app_kb_bindings (
  app_id          VARCHAR(64) NOT NULL,
  kb_id           VARCHAR(64) NOT NULL,
  top_k           INT DEFAULT 5,
  score_threshold FLOAT DEFAULT 0.5,
  search_method   VARCHAR(32) DEFAULT 'hybrid',
  rerank_enabled  TINYINT DEFAULT 0,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (app_id, kb_id),
  INDEX idx_kb_id (kb_id),
  CONSTRAINT fk_akb_app FOREIGN KEY (app_id) REFERENCES apps(id) ON DELETE CASCADE,
  CONSTRAINT fk_akb_kb  FOREIGN KEY (kb_id)  REFERENCES knowledge_bases(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS agent_runs (
  id              VARCHAR(64) PRIMARY KEY,
  execution_id    VARCHAR(64) NOT NULL,
  agent_name      VARCHAR(128) NOT NULL,
  agent_type      VARCHAR(64) NOT NULL,
  agent_index     TINYINT DEFAULT 0,
  status          VARCHAR(32) DEFAULT 'idle',
  system_prompt   LONGTEXT,
  model           VARCHAR(128),
  turn_count      INT DEFAULT 0,
  input_tokens    INT DEFAULT 0,
  output_tokens   INT DEFAULT 0,
  started_at      DATETIME,
  finished_at     DATETIME,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_execution_id (execution_id),
  CONSTRAINT fk_ar_exec FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS agent_messages (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  execution_id  VARCHAR(64) NOT NULL,
  run_id        VARCHAR(64),
  from_agent    VARCHAR(128),
  to_agent      VARCHAR(128),
  role          VARCHAR(32) NOT NULL,
  content       LONGTEXT NOT NULL,
  turn          INT DEFAULT 0,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_execution_id (execution_id),
  INDEX idx_run_id       (run_id),
  INDEX idx_exec_turn    (execution_id, turn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS execution_checkpoints (
  id              VARCHAR(64) PRIMARY KEY,
  execution_id    VARCHAR(64) NOT NULL,
  node_id         VARCHAR(64) NOT NULL,
  state           LONGTEXT NOT NULL,
  completed_nodes LONGTEXT,
  checkpoint_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_execution_id (execution_id),
  CONSTRAINT fk_ckpt_exec FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS eval_datasets (
  id          VARCHAR(64) PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  description TEXT,
  app_id      VARCHAR(64),
  created_by  VARCHAR(64),
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_app_id (app_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS eval_cases (
  id              VARCHAR(64) PRIMARY KEY,
  dataset_id      VARCHAR(64) NOT NULL,
  question        LONGTEXT NOT NULL,
  expected_answer LONGTEXT,
  context         LONGTEXT,
  tags            VARCHAR(512),
  difficulty      VARCHAR(16) DEFAULT 'medium',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_dataset_id (dataset_id),
  CONSTRAINT fk_ec_ds FOREIGN KEY (dataset_id) REFERENCES eval_datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS eval_runs (
  id              VARCHAR(64) PRIMARY KEY,
  dataset_id      VARCHAR(64) NOT NULL,
  app_id          VARCHAR(64),
  model           VARCHAR(128),
  label           VARCHAR(255),
  status          VARCHAR(32) DEFAULT 'pending',
  total_cases     INT DEFAULT 0,
  passed_cases    INT DEFAULT 0,
  avg_score       FLOAT,
  avg_latency_ms  INT,
  total_tokens    INT DEFAULT 0,
  total_cost      DOUBLE DEFAULT 0,
  started_at      DATETIME,
  finished_at     DATETIME,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_dataset_id (dataset_id),
  INDEX idx_app_model  (app_id, model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS eval_results (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id          VARCHAR(64) NOT NULL,
  case_id         VARCHAR(64) NOT NULL,
  actual_answer   LONGTEXT,
  score           FLOAT,
  passed          TINYINT DEFAULT 0,
  eval_method     VARCHAR(32),
  judge_reasoning TEXT,
  latency_ms      INT,
  input_tokens    INT,
  output_tokens   INT,
  error           TEXT,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_run_id  (run_id),
  INDEX idx_case_id (case_id),
  CONSTRAINT fk_er_run FOREIGN KEY (run_id) REFERENCES eval_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS organizations (
  id          VARCHAR(64) PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  plan        VARCHAR(32) DEFAULT 'free',
  quota_tokens BIGINT DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_org_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS org_members (
  org_id    VARCHAR(64) NOT NULL,
  user_id   VARCHAR(64) NOT NULL,
  role      VARCHAR(32) DEFAULT 'member',
  joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (org_id, user_id),
  INDEX idx_user_id (user_id),
  CONSTRAINT fk_om_org  FOREIGN KEY (org_id)  REFERENCES organizations(id) ON DELETE CASCADE,
  CONSTRAINT fk_om_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS api_keys (
  id             VARCHAR(64) PRIMARY KEY,
  key_hash       VARCHAR(128) NOT NULL,
  key_prefix     VARCHAR(16),
  name           VARCHAR(255),
  user_id        VARCHAR(64) NOT NULL,
  scopes         VARCHAR(512) DEFAULT '*',
  app_id         VARCHAR(64),
  rate_limit_rpm INT DEFAULT 60,
  token_budget   BIGINT,
  tokens_used    BIGINT DEFAULT 0,
  is_active      TINYINT DEFAULT 1,
  last_used_at   DATETIME,
  expires_at     DATETIME,
  created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_key_hash (key_hash),
  INDEX idx_user_id (user_id),
  INDEX idx_active  (is_active, expires_at),
  CONSTRAINT fk_ak_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS audit_logs (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id       VARCHAR(64),
  api_key_id    VARCHAR(64),
  action        VARCHAR(128) NOT NULL,
  resource_type VARCHAR(64),
  resource_id   VARCHAR(64),
  resource_name VARCHAR(255),
  changes       LONGTEXT,
  result        VARCHAR(32) DEFAULT 'success',
  error_msg     TEXT,
  ip_address    VARCHAR(45),
  user_agent    VARCHAR(512),
  request_id    VARCHAR(64),
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_id    (user_id, created_at),
  INDEX idx_resource   (resource_type, resource_id),
  INDEX idx_action     (action, created_at),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS usage_stats (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id       VARCHAR(64) NOT NULL,
  app_id        VARCHAR(64),
  model         VARCHAR(128),
  stat_date     DATE NOT NULL,
  input_tokens  BIGINT DEFAULT 0,
  output_tokens BIGINT DEFAULT 0,
  total_tokens  BIGINT DEFAULT 0,
  sessions      INT DEFAULT 0,
  messages      INT DEFAULT 0,
  tool_calls    INT DEFAULT 0,
  rag_queries   INT DEFAULT 0,
  workflow_runs INT DEFAULT 0,
  cost          DOUBLE DEFAULT 0,
  UNIQUE KEY uk_user_app_date (user_id, app_id, stat_date, model),
  INDEX idx_user_date (user_id, stat_date),
  INDEX idx_app_date  (app_id, stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS scheduled_triggers (
  id              VARCHAR(64) PRIMARY KEY,
  workflow_id     VARCHAR(64) NOT NULL,
  app_id          VARCHAR(64),
  created_by      VARCHAR(64),
  name            VARCHAR(255) NOT NULL,
  cron_expr       VARCHAR(128) NOT NULL,
  timezone        VARCHAR(64) DEFAULT 'Asia/Shanghai',
  inputs          LONGTEXT,
  is_enabled      TINYINT DEFAULT 1,
  last_run_at     DATETIME,
  last_run_status VARCHAR(32),
  next_run_at     DATETIME,
  run_count       INT DEFAULT 0,
  fail_count      INT DEFAULT 0,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_workflow_id  (workflow_id),
  INDEX idx_next_enabled (is_enabled, next_run_at),
  CONSTRAINT fk_st_workflow FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


async def get_db() -> Any:
    """Return the active DB connection (aiosqlite.Connection or _MySQLDB)."""
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def _migrate(db: Any) -> None:
    """Incremental schema migrations (columns added after initial release)."""
    cur = await db.execute("PRAGMA table_info(apps)")
    rows = await cur.fetchall()
    # Works for both backends: aiosqlite.Row[1] == row["name"] for MySQL dict rows
    cols: set[str] = set()
    for r in rows:
        cols.add(r["name"] if isinstance(r, dict) else r[1])

    migrations = []
    if "opening_msg" not in cols:
        migrations.append("ALTER TABLE apps ADD COLUMN opening_msg TEXT DEFAULT ''")
    if "model_params" not in cols:
        migrations.append("ALTER TABLE apps ADD COLUMN model_params JSON DEFAULT '{}'")

    # users table migration (for existing DB without it)
    try:
        await db.execute("SELECT 1 FROM users LIMIT 1")
    except Exception:
        migrations.append(
            "CREATE TABLE IF NOT EXISTS users ("
            "id VARCHAR(64) PRIMARY KEY, username VARCHAR(128) NOT NULL UNIQUE, "
            "password_hash VARCHAR(256) NOT NULL, display_name VARCHAR(255) DEFAULT '', "
            "is_admin TINYINT DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    # ── Phase 0: FK 索引（幂等，索引不存在时才创建）────────────────────────────
    _phase0_indexes = [
        ("app_sessions",      "idx_app_id",          "ALTER TABLE app_sessions ADD INDEX idx_app_id (app_id)"),
        ("app_messages",      "idx_session_id",       "ALTER TABLE app_messages ADD INDEX idx_session_id (session_id)"),
        ("app_messages",      "idx_session_created",  "ALTER TABLE app_messages ADD INDEX idx_session_created (session_id, created_at)"),
        ("chat_messages",     "idx_session_id",       "ALTER TABLE chat_messages ADD INDEX idx_session_id (session_id)"),
        ("chat_messages",     "idx_session_created",  "ALTER TABLE chat_messages ADD INDEX idx_session_created (session_id, created_at)"),
        ("executions",        "idx_workflow_id",      "ALTER TABLE executions ADD INDEX idx_workflow_id (workflow_id)"),
        ("executions",        "idx_status_started",   "ALTER TABLE executions ADD INDEX idx_status_started (status, started_at)"),
        ("trace_spans",       "idx_execution_id",     "ALTER TABLE trace_spans ADD INDEX idx_execution_id (execution_id)"),
        ("trace_spans",       "idx_exec_start",       "ALTER TABLE trace_spans ADD INDEX idx_exec_start (execution_id, start_time)"),
        ("workflow_versions", "idx_workflow_id",      "ALTER TABLE workflow_versions ADD INDEX idx_workflow_id (workflow_id)"),
        ("skill_invocations", "idx_skill_id",         "ALTER TABLE skill_invocations ADD INDEX idx_skill_id (skill_id)"),
        ("skill_invocations", "idx_skill_invoked",    "ALTER TABLE skill_invocations ADD INDEX idx_skill_invoked (skill_id, invoked_at)"),
        ("tool_usages",       "idx_tool_created",     "ALTER TABLE tool_usages ADD INDEX idx_tool_created (tool_name, created_at)"),
    ]
    # Only applicable for MySQL (SQLite ignores ADD INDEX syntax)
    global _db_type
    if _db_type == "mysql":
        for tbl, idx_name, sql in _phase0_indexes:
            migrations.append(sql)

    # ── Phase 1A: chat_messages 新字段 ──────────────────────────────────────────
    cur2 = await db.execute("PRAGMA table_info(chat_messages)")
    chat_msg_cols: set[str] = set()
    for r in await cur2.fetchall():
        chat_msg_cols.add(r["name"] if isinstance(r, dict) else r[1])

    if "thinking_content" not in chat_msg_cols:
        migrations.append("ALTER TABLE chat_messages ADD COLUMN thinking_content LONGTEXT NULL")
    if "model" not in chat_msg_cols:
        migrations.append("ALTER TABLE chat_messages ADD COLUMN model VARCHAR(128) NULL")
    if "input_tokens" not in chat_msg_cols:
        migrations.append("ALTER TABLE chat_messages ADD COLUMN input_tokens INT DEFAULT 0")
    if "output_tokens" not in chat_msg_cols:
        migrations.append("ALTER TABLE chat_messages ADD COLUMN output_tokens INT DEFAULT 0")
    if "latency_ms" not in chat_msg_cols:
        migrations.append("ALTER TABLE chat_messages ADD COLUMN latency_ms INT DEFAULT 0")
    if "tool_rounds" not in chat_msg_cols:
        migrations.append("ALTER TABLE chat_messages ADD COLUMN tool_rounds TINYINT DEFAULT 0")

    # ── Phase 1B: app_messages 新字段 ───────────────────────────────────────────
    cur3 = await db.execute("PRAGMA table_info(app_messages)")
    app_msg_cols: set[str] = set()
    for r in await cur3.fetchall():
        app_msg_cols.add(r["name"] if isinstance(r, dict) else r[1])

    if "thinking_content" not in app_msg_cols:
        migrations.append("ALTER TABLE app_messages ADD COLUMN thinking_content LONGTEXT NULL")
    if "model" not in app_msg_cols:
        migrations.append("ALTER TABLE app_messages ADD COLUMN model VARCHAR(128) NULL")
    if "input_tokens" not in app_msg_cols:
        migrations.append("ALTER TABLE app_messages ADD COLUMN input_tokens INT DEFAULT 0")
    if "output_tokens" not in app_msg_cols:
        migrations.append("ALTER TABLE app_messages ADD COLUMN output_tokens INT DEFAULT 0")
    if "latency_ms" not in app_msg_cols:
        migrations.append("ALTER TABLE app_messages ADD COLUMN latency_ms INT DEFAULT 0")
    if "tool_rounds" not in app_msg_cols:
        migrations.append("ALTER TABLE app_messages ADD COLUMN tool_rounds TINYINT DEFAULT 0")

    # ── Phase 1C: 会话用户归属 ───────────────────────────────────────────────────
    cur4 = await db.execute("PRAGMA table_info(chat_sessions)")
    chat_sess_cols: set[str] = set()
    for r in await cur4.fetchall():
        chat_sess_cols.add(r["name"] if isinstance(r, dict) else r[1])
    if "user_id" not in chat_sess_cols:
        migrations.append("ALTER TABLE chat_sessions ADD COLUMN user_id VARCHAR(64) NULL")

    cur5 = await db.execute("PRAGMA table_info(app_sessions)")
    app_sess_cols: set[str] = set()
    for r in await cur5.fetchall():
        app_sess_cols.add(r["name"] if isinstance(r, dict) else r[1])
    if "user_id" not in app_sess_cols:
        migrations.append("ALTER TABLE app_sessions ADD COLUMN user_id VARCHAR(64) NULL")

    if "created_by" not in cols:  # cols = apps table columns from top
        migrations.append("ALTER TABLE apps ADD COLUMN created_by VARCHAR(64) NULL")

    # ── Phase 1D: executions 关联字段 ────────────────────────────────────────────
    cur6 = await db.execute("PRAGMA table_info(executions)")
    exec_cols: set[str] = set()
    for r in await cur6.fetchall():
        exec_cols.add(r["name"] if isinstance(r, dict) else r[1])
    if "app_id" not in exec_cols:
        migrations.append("ALTER TABLE executions ADD COLUMN app_id VARCHAR(64) NULL")
    if "session_id" not in exec_cols:
        migrations.append("ALTER TABLE executions ADD COLUMN session_id VARCHAR(64) NULL")
    if "triggered_by" not in exec_cols:
        migrations.append("ALTER TABLE executions ADD COLUMN triggered_by VARCHAR(64) NULL")

    for sql in migrations:
        try:
            await db.execute(sql)
        except Exception as e:
            # Column/index may already exist — safe to ignore
            logger.debug("Migration skipped (%s): %s", e, sql[:80])
    if migrations:
        await db.commit()


async def init_db(db_path: str) -> None:
    """Initialise the database.  db_path is either a file path (SQLite)
    or a mysql+aiomysql:// DSN (MySQL)."""
    global _db, _db_type

    if db_path.startswith("mysql"):
        import aiomysql  # type: ignore
        import re as _re
        # Parse DSN: mysql+aiomysql://user:pass@host:port/dbname?...
        m = _re.match(
            r'mysql\+aiomysql://([^:@]*)(?::([^@]*))?@([^:/]+)(?::(\d+))?/([^?]+)',
            db_path
        )
        if not m:
            raise ValueError(f"Cannot parse MySQL DSN: {db_path}")
        user, password, host, port, database = (
            m.group(1), m.group(2) or "", m.group(3),
            int(m.group(4) or 3306), m.group(5).split('?')[0]
        )
        pool = await aiomysql.create_pool(
            host=host, port=port, user=user, password=password,
            db=database, charset="utf8mb4",
            autocommit=True, minsize=1, maxsize=10,
        )
        _db_type = "mysql"
        _db = _MySQLDB(pool)
        await _db.executescript(MYSQL_SCHEMA_SQL)
        await _migrate(_db)
        logger.info("MySQL backend initialised: %s@%s:%s/%s", user, host, port, database)
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await conn.executescript(SCHEMA_SQL)
        await conn.commit()
        _db_type = "sqlite"
        _db = conn
        await _migrate(_db)
        logger.info("SQLite backend initialised: %s", db_path)


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None
