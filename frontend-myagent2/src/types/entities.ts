// ===== 工作流列表项 =====
export interface WorkflowListItem {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'draft' | 'archived';
  version: string;
  nodeCount: number;
  edgeCount: number;
  lastRunAt?: string;
  lastRunStatus?: 'success' | 'failed' | 'running';
  successRate?: number;
  createdAt: string;
  updatedAt: string;
  tags: string[];
}

// ===== 模型配置 =====
export interface ModelConfig {
  id: string;
  name: string;
  provider: 'ollama' | 'openai' | 'anthropic' | 'deepseek' | 'custom';
  endpoint: string;
  modelId: string;
  apiKeyRef?: string;
  contextWindow: number;
  defaultTemperature: number;
  defaultTopP: number;
  defaultMaxTokens: number;
  inputPricePerMToken: number;
  outputPricePerMToken: number;
  capabilities: {
    functionCalling: boolean;
    streaming: boolean;
    vision: boolean;
  };
  usageTags: ('inference' | 'compression' | 'embedding')[];
  isDefault: boolean;
  status: 'online' | 'offline' | 'unconfigured';
  createdAt: string;
  updatedAt: string;
}

// ===== 密钥 =====
export interface SecretItem {
  name: string;
  description: string;
  reference: string;
  createdAt: string;
  updatedAt: string;
}

// ===== Skill =====
export interface Skill {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  content: string;
  is_builtin: boolean;
  source_type: string;
  source_path: string;
  source_repo: string;
  allowed_tools: string[];
  arguments: string[];
  argument_hint: string;
  when_to_use: string;
  context_mode: string;
  agent: string;
  model: string;
  variables: string[];
  required_tools: string[];
  migration_status: string;
  migration_notes: string;
  content_hash: string;
  created_at: string;
  updated_at: string;
}

// ===== Prompt 模板 =====
export interface PromptTemplate {
  id: string;
  name: string;
  type: 'system' | 'user' | 'output_format' | 'snippet';
  content: string;
  variables: string[];
  tags: string[];
  source: 'builtin' | 'user';
  usageCount: number;
  createdAt: string;
  updatedAt: string;
}

// ===== 工具 =====
export interface ToolParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object';
  description: string;
  required: boolean;
  default?: unknown;
}

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  source: 'builtin' | 'mcp' | 'custom';
  mcpServer?: string;
  parameters: ToolParameter[];
  permissionLevel: 'auto_allow' | 'always_ask' | 'deny';
  enabled: boolean;
  executionCount: number;
  avgDurationMs: number;
  lastUsedAt?: string;
}

// ===== MCP Server =====
export interface MCPServerConfig {
  id: string;
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  autoStart: boolean;
  timeout: number;
  status: 'running' | 'stopped' | 'error';
  pid?: number;
  tools: ToolDefinition[];
  connectedAt?: string;
  callCount: number;
  lastError?: string;
}

// ===== 执行记录 =====
export interface ExecutionRecord {
  id: string;
  workflowId: string;
  workflowName: string;
  version: string;
  status: 'running' | 'success' | 'failed' | 'cancelled' | 'timeout';
  currentNode?: string;
  progress?: { current: number; total: number };
  totalDurationMs: number;
  totalTokens: number;
  cost: number;
  error?: string;
  startedAt: string;
  finishedAt?: string;
}

// ===== 知识库 =====
export interface KnowledgeItem {
  id: string;
  name: string;
  type: 'file' | 'text' | 'url';
  content: string;
  sizeBytes: number;
  scope: 'global' | string[];
  createdAt: string;
  updatedAt: string;
}

// ===== 系统设置 =====
export interface SystemSettings {
  maxConcurrentWorkflows: number;
  maxConcurrentLLMCalls: number;
  maxConcurrentTools: number;
  llmTimeoutSeconds: number;
  toolTimeoutSeconds: number;
  workflowTimeoutSeconds: number;
  sandboxMode: 'subprocess' | 'docker';
  sandboxWorkDir: string;
  maxOutputSize: number;
  compressionStrategy: 'auto' | 'sliding_window' | 'summarize';
  compressionThreshold: number;
  compressionModel: string;
}
