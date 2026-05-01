import type { Node, Edge } from '@xyflow/react';

// ===== 节点类型 =====
export const NodeType = {
  START: 'start',
  LLM: 'llm',
  TOOL: 'tool',
  CONDITION: 'condition',
  LOOP: 'loop',
  SUBFLOW: 'subflow',
  MERGE: 'merge',
  VARIABLE: 'variable',
  HUMAN: 'human',
  SKILL: 'skill',
  END: 'end',
} as const;

export type NodeType = (typeof NodeType)[keyof typeof NodeType];

// ===== 通用节点数据 =====
export interface BaseNodeData extends Record<string, unknown> {
  label: string;
  description?: string;
  timeout?: number;
  retryCount?: number;
  onError?: 'stop' | 'continue' | 'fallback';
}

// ===== LLM 节点 =====
export interface LLMNodeData extends BaseNodeData {
  systemPrompt: string;
  userPromptTemplate: string;
  model: string;
  temperature: number;
  topP: number;
  maxTokens: number;
  enableTools: boolean;
  allowedTools: string[];
  outputFormat: 'text' | 'json' | 'markdown';
  outputVariable: string;
  jsonSchema?: object;
}

// ===== 工具节点 =====
export interface ToolNodeData extends BaseNodeData {
  toolName: string;
  toolParams: Record<string, unknown>;
  paramMapping: Record<string, string>;
  outputVariable: string;
  maxResultSize?: number;
}

// ===== 条件节点 =====
export interface ConditionBranch {
  id: string;
  label: string;
  condition: string;
  targetHandle: string;
}

export interface ConditionNodeData extends BaseNodeData {
  branches: ConditionBranch[];
  defaultBranch: string;
}

// ===== 循环节点 =====
export interface LoopNodeData extends BaseNodeData {
  maxIterations: number;
  exitCondition: string;
  contextVariable: string;
  appendMode: 'replace' | 'append';
}

// ===== 人工审批节点 =====
export interface HumanNodeData extends BaseNodeData {
  interactionType: 'approve' | 'input' | 'select';
  displayTemplate: string;
  timeoutSeconds?: number;
  timeoutAction: 'approve' | 'reject' | 'skip';
  outputVariable: string;
}

// ===== 开始/结束节点 =====
export interface StartNodeData extends BaseNodeData {
  outputs: string[];
}

export interface EndNodeData extends BaseNodeData {
  outputs: string[];
}

// ===== 变量节点 =====
export interface VariableNodeData extends BaseNodeData {
  expression: string;
  outputVariable: string;
}

// ===== Skill 节点 =====
export interface SkillNodeData extends BaseNodeData {
  skillId: string;
  skillName: string;
  sourceType: string;
  contextMode: string;
  argsTemplate: string;
  modelOverride: string;
  allowedTools: string[];
  whenToUse: string;
  migrationStatus: string;
  outputVariable: string;
}

// ===== React Flow 节点类型 =====
export type FlowNode = Node<BaseNodeData | LLMNodeData | ToolNodeData | ConditionNodeData | LoopNodeData | HumanNodeData | StartNodeData | EndNodeData | VariableNodeData | SkillNodeData>;
export type FlowEdge = Edge;

// ===== 工作流定义 =====
export interface WorkflowVariable {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  default?: unknown;
  description?: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  version: string;
  variables: Record<string, WorkflowVariable>;
  nodes: FlowNode[];
  edges: FlowEdge[];
}

// ===== 节点库元数据 =====
export interface NodeTemplate {
  type: NodeType;
  label: string;
  icon: string;
  color: string;
  category: 'basic' | 'logic' | 'skill' | 'advanced';
  defaultData: BaseNodeData;
}
