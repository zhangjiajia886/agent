#!/bin/bash
# TTS 应用全流程自动化测试脚本
# 用法: ./test.sh [后端地址，默认 http://localhost:8000]

BASE_URL="${1:-http://localhost:8000}"
API="${BASE_URL}/api/v1"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

PASS=0
FAIL=0
TOKEN=""
SESSION_ID=""

# ── 工具函数 ────────────────────────────────────────────

pass() { echo -e "  ${GREEN}✅ PASS${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}❌ FAIL${NC} $1"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}⚠️  SKIP${NC} $1"; }
section() { echo -e "\n${CYAN}${BOLD}▶ $1${NC}"; }

# 发送请求并返回响应体
req() {
  local method=$1 url=$2
  shift 2
  curl -s -X "$method" "$url" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    "$@"
}

# 带 token 的请求
auth_req() {
  local method=$1 url=$2
  shift 2
  req "$method" "$url" -H "Authorization: Bearer $TOKEN" "$@"
}

# 检查 HTTP 状态码
http_status() {
  local method=$1 url=$2
  shift 2
  curl -s -o /dev/null -w "%{http_code}" -X "$method" "$url" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    "$@"
}

# 从 JSON 中提取字段值
jq_get() {
  echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null
}

# ── 测试用例 ────────────────────────────────────────────

test_health() {
  section "健康检查"
  resp=$(req GET "$BASE_URL/health")
  status=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  if [ "$status" = "healthy" ]; then
    pass "GET /health → status=healthy"
  else
    fail "GET /health → 响应: $resp"
  fi
}

test_auth() {
  section "认证接口"

  # 生成唯一用户名避免冲突
  TS=$(date +%s)
  USERNAME="testuser_${TS}"
  EMAIL="test_${TS}@example.com"
  PASSWORD="Test123456!"

  # 注册
  resp=$(req POST "$API/auth/register" \
    -d "{\"username\":\"$USERNAME\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"Test User\"}")
  uid=$(jq_get "$resp" "id")
  if [ -n "$uid" ] && [ "$uid" != "None" ]; then
    pass "POST /auth/register → uid=$uid, username=$USERNAME"
  else
    fail "POST /auth/register → $resp"
  fi

  # 登录（OAuth2 form）
  resp=$(curl -s -X POST "$API/auth/login" \
    -d "username=$USERNAME&password=$PASSWORD" \
    -H "Content-Type: application/x-www-form-urlencoded")
  TOKEN=$(jq_get "$resp" "access_token")
  if [ -n "$TOKEN" ] && [ "$TOKEN" != "None" ]; then
    pass "POST /auth/login → token 获取成功"
  else
    fail "POST /auth/login → $resp"
    return
  fi

  # 获取当前用户信息
  resp=$(auth_req GET "$API/auth/me")
  me_user=$(jq_get "$resp" "username")
  if [ "$me_user" = "$USERNAME" ]; then
    pass "GET /auth/me → username=$me_user"
  else
    fail "GET /auth/me → $resp"
  fi
}

test_voice_models() {
  section "声音模型"
  [ -z "$TOKEN" ] && { warn "未登录，跳过"; return; }

  resp=$(auth_req GET "$API/voice-models/?skip=0&limit=10")
  total=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',d.get('items','ERR')))" 2>/dev/null)
  if echo "$resp" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    pass "GET /voice-models/ → 响应合法 JSON"
  else
    fail "GET /voice-models/ → $resp"
  fi
}

test_tts() {
  section "TTS 合成"
  [ -z "$TOKEN" ] && { warn "未登录，跳过"; return; }

  resp=$(auth_req POST "$API/tts/synthesize" \
    -d '{"text":"你好，这是一段测试语音合成文本","format":"mp3","latency":"balanced"}')
  task_id=$(jq_get "$resp" "task_id")
  status=$(jq_get "$resp" "status")

  if [ -n "$task_id" ] && [ "$task_id" != "None" ]; then
    pass "POST /tts/synthesize → task_id=$task_id, status=$status"
  else
    fail "POST /tts/synthesize → $resp"
    return
  fi

  # 查询任务列表
  resp=$(auth_req GET "$API/tts/tasks?skip=0&limit=5")
  if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list)" 2>/dev/null; then
    count=$(echo "$resp" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    pass "GET /tts/tasks → $count 条任务"
  else
    fail "GET /tts/tasks → $resp"
  fi

  # 查询任务详情
  resp=$(auth_req GET "$API/tts/tasks/$task_id")
  detail_id=$(jq_get "$resp" "id")
  if [ "$detail_id" = "$task_id" ]; then
    pass "GET /tts/tasks/$task_id → 任务详情正确"
  else
    fail "GET /tts/tasks/$task_id → $resp"
  fi
}

test_chat() {
  section "聊天陪聊"
  [ -z "$TOKEN" ] && { warn "未登录，跳过"; return; }

  # 创建会话
  resp=$(auth_req POST "$API/chat/sessions" \
    -d '{"title":"自动化测试会话","system_prompt":"你是一个测试助手，请简短回复。"}')
  SESSION_ID=$(jq_get "$resp" "id")
  if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "None" ]; then
    pass "POST /chat/sessions → session_id=$SESSION_ID"
  else
    fail "POST /chat/sessions → $resp"
    return
  fi

  # 获取会话列表
  resp=$(auth_req GET "$API/chat/sessions")
  if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list)" 2>/dev/null; then
    count=$(echo "$resp" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    pass "GET /chat/sessions → $count 个会话"
  else
    fail "GET /chat/sessions → $resp"
  fi

  # 获取会话详情（含 messages 预加载验证）
  resp=$(auth_req GET "$API/chat/sessions/$SESSION_ID")
  sid=$(jq_get "$resp" "id")
  if [ "$sid" = "$SESSION_ID" ]; then
    pass "GET /chat/sessions/$SESSION_ID → 详情正确"
  else
    fail "GET /chat/sessions/$SESSION_ID → $resp"
  fi

  # 非流式发送消息（会调用 LLM，可能因网络原因失败，不计入强制 FAIL）
  echo -e "  ${YELLOW}→${NC} 非流式发送消息（调用 LLM，视网络情况）..."
  resp=$(auth_req POST "$API/chat/send" \
    -d "{\"session_id\":$SESSION_ID,\"message\":\"你好，请用一句话介绍自己\"}" \
    --max-time 30)
  role=$(jq_get "$resp" "role")
  content=$(jq_get "$resp" "content")
  if [ "$role" = "assistant" ] && [ -n "$content" ] && [ "$content" != "None" ]; then
    pass "POST /chat/send → LLM 回复: ${content:0:40}..."
  else
    warn "POST /chat/send → LLM 不可达或超时（$resp），跳过"
  fi

  # SSE 流式接口连通性测试（只验证响应头，不等待完整流）
  echo -e "  ${YELLOW}→${NC} SSE 流式接口连通性测试..."
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$API/chat/stream" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"session_id\":$SESSION_ID,\"message\":\"hi\"}" \
    --max-time 5 \
    -H "Accept: text/event-stream")
  if [ "$http_code" = "200" ]; then
    pass "POST /chat/stream → HTTP 200（SSE 已建立连接）"
  else
    warn "POST /chat/stream → HTTP $http_code（LLM 不可达或超时）"
  fi

  # 更新会话标题
  resp=$(auth_req PATCH "$API/chat/sessions/$SESSION_ID" \
    -d '{"title":"自动化测试（已更新）"}')
  new_title=$(jq_get "$resp" "title")
  if echo "$new_title" | grep -q "已更新"; then
    pass "PATCH /chat/sessions/$SESSION_ID → 标题更新成功"
  else
    fail "PATCH /chat/sessions/$SESSION_ID → $resp"
  fi

  # 删除会话
  resp=$(auth_req DELETE "$API/chat/sessions/$SESSION_ID")
  msg=$(jq_get "$resp" "message")
  if echo "$msg" | grep -qi "deleted"; then
    pass "DELETE /chat/sessions/$SESSION_ID → 删除成功"
  else
    fail "DELETE /chat/sessions/$SESSION_ID → $resp"
  fi
}

test_error_cases() {
  section "错误处理"

  # 未授权访问
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/me")
  if [ "$code" = "401" ]; then
    pass "无 token 访问 /auth/me → 401"
  else
    fail "无 token 访问 /auth/me → HTTP $code（期望 401）"
  fi

  # 不存在资源
  [ -z "$TOKEN" ] && return
  code=$(http_status GET "$API/chat/sessions/999999")
  if [ "$code" = "404" ]; then
    pass "访问不存在会话 → 404"
  else
    fail "访问不存在会话 → HTTP $code（期望 404）"
  fi
}

# ── 汇总 ────────────────────────────────────────────────

summary() {
  local total=$((PASS + FAIL))
  echo ""
  echo "═══════════════════════════════════════════"
  echo -e "  测试结果: ${BOLD}$total${NC} 项"
  echo -e "  ${GREEN}通过: $PASS${NC}  ${RED}失败: $FAIL${NC}"
  echo "═══════════════════════════════════════════"
  echo ""
  [ $FAIL -eq 0 ] && echo -e "${GREEN}🎉 所有测试通过！${NC}" || echo -e "${RED}❌ 有 $FAIL 项失败，请检查日志${NC}"
  echo ""
  [ $FAIL -gt 0 ] && exit 1 || exit 0
}

# ── 入口 ────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       TTS 应用全流程自动化测试           ║"
echo "║  目标: $BASE_URL"
echo "╚══════════════════════════════════════════╝"

test_health
test_auth
test_voice_models
test_tts
test_chat
test_error_cases
summary
