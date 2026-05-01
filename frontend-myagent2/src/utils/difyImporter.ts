import yaml from 'js-yaml';

// ── Dify DSL types (partial) ──────────────────────────────────────────────────

interface DifyVarRef { variable_selector: string[]; comparison_operator: string; value: string }
interface DifyCase { id: string; logical_operator?: string; conditions?: DifyVarRef[] }
interface DifyClass { id: string; name: string }
interface DifyPromptItem { role: string; text: string }
interface DifyOutputsMap { [key: string]: { type?: string } }

interface DifyNodeData {
  type: string;
  title?: string;
  desc?: string;
  // start
  variables?: Array<{ variable: string; label?: string; type?: string; required?: boolean }>;
  // llm
  model?: { name?: string; provider?: string; mode?: string; completion_params?: Record<string, unknown> };
  prompt_template?: DifyPromptItem[];
  prompt_list?: DifyPromptItem[];
  system_prompt?: string;
  // if-else
  cases?: DifyCase[];
  conditions?: DifyVarRef[];
  // question-classifier
  classes?: DifyClass[];
  query_variable_selector?: string[];
  // iteration
  iterator_selector?: string[];
  output_selector?: string[];
  // code
  code?: string;
  code_language?: string;
  // template-transform
  template?: string;
  // outputs (end / code)
  outputs?: DifyOutputsMap | string[];
}

interface DifyNode {
  id: string;
  position?: { x: number; y: number };
  positionAbsolute?: { x: number; y: number };
  data: DifyNodeData;
}

interface DifyEdge {
  id: string;
  source: string;
  sourceHandle: string;
  target: string;
  targetHandle: string;
}

interface DifyGraph { nodes: DifyNode[]; edges: DifyEdge[] }

interface DifyDSL {
  app?: { name?: string; description?: string; mode?: string };
  workflow?: { graph?: DifyGraph };
}

// ── Conversion helpers ────────────────────────────────────────────────────────

/** Convert Dify variable reference {{#nodeId.field#}} → {{nodeId_field}} */
function convertVarRefs(text: string): string {
  return text.replace(/\{\{#([^.#]+)\.([^#]+)#\}\}/g, (_, nid, field) => `{{${nid}_${field}}}`);
}

const DIFY_TYPE_MAP: Record<string, string> = {
  start: 'start',
  end: 'end',
  answer: 'end',
  llm: 'llm',
  'if-else': 'condition',
  'question-classifier': 'condition',
  iteration: 'loop',
  code: 'variable',
  'template-transform': 'variable',
  'http-request': 'tool',
  'knowledge-retrieval': 'tool',
};

function convertNodeData(node: DifyNode): Record<string, unknown> {
  const d = node.data;
  const label = d.title ?? d.type ?? 'node';
  const base: Record<string, unknown> = { label };

  switch (d.type) {
    case 'start': {
      base.outputs = (d.variables ?? []).map(v => v.variable);
      return base;
    }

    case 'end':
    case 'answer': {
      const outs = d.outputs;
      if (Array.isArray(outs)) {
        base.outputs = outs;
      } else if (outs && typeof outs === 'object') {
        base.outputs = Object.keys(outs);
      } else {
        base.outputs = [];
      }
      return base;
    }

    case 'llm': {
      const allPrompts = [...(d.prompt_template ?? []), ...(d.prompt_list ?? [])];
      const systemText = allPrompts.find(p => p.role === 'system')?.text ?? d.system_prompt ?? '你是一个有帮助的助手。';
      const userText = allPrompts.find(p => p.role === 'user')?.text ?? '{{user_input}}';
      const params = d.model?.completion_params ?? {};
      return {
        ...base,
        model: d.model?.name ?? 'qwen3-32b',
        systemPrompt: convertVarRefs(systemText),
        userPromptTemplate: convertVarRefs(userText),
        temperature: (params.temperature as number) ?? 0.7,
        topP: (params.top_p as number) ?? 0.9,
        maxTokens: (params.max_tokens as number) ?? 2048,
        outputFormat: 'text',
        outputVariable: 'result',
      };
    }

    case 'if-else': {
      const cases = d.cases ?? [];
      const branches = cases.map((c, i) => {
        const cond = (c.conditions ?? []).map(r => {
          const varRef = r.variable_selector?.length ? r.variable_selector.join('.') : 'input';
          return `{{${varRef}}} ${r.comparison_operator ?? '=='} ${r.value ?? ''}`;
        }).join(' && ') || 'true';
        return { id: c.id ?? `b${i + 1}`, label: `分支 ${i + 1}`, condition: cond, targetHandle: c.id ?? `b${i + 1}` };
      });
      branches.push({ id: 'false', label: '否 (默认)', condition: 'false', targetHandle: 'false' });
      return { ...base, branches, defaultBranch: 'false' };
    }

    case 'question-classifier': {
      const classes = d.classes ?? [];
      const branches = classes.map(c => ({
        id: c.id, label: c.name, condition: c.name, targetHandle: c.id,
      }));
      return { ...base, branches, defaultBranch: branches[0]?.id ?? 'b1' };
    }

    case 'iteration': {
      return { ...base, maxIterations: 10, exitCondition: '', contextVariable: 'loop_context', appendMode: 'append' };
    }

    case 'code': {
      const outs = d.outputs && !Array.isArray(d.outputs) ? Object.keys(d.outputs) : [];
      return {
        ...base,
        expression: convertVarRefs(d.code ?? ''),
        outputVariable: outs[0] ?? 'code_result',
      };
    }

    case 'template-transform': {
      return {
        ...base,
        expression: convertVarRefs(d.template ?? ''),
        outputVariable: 'template_result',
      };
    }

    case 'http-request': {
      return { ...base, toolName: 'http_request', toolParams: {}, paramMapping: {}, outputVariable: 'http_result' };
    }

    case 'knowledge-retrieval': {
      return { ...base, toolName: 'knowledge_retrieval', toolParams: {}, paramMapping: {}, outputVariable: 'retrieval_result' };
    }

    default:
      return { ...base, expression: '', outputVariable: 'result' };
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

export interface ImportResult {
  name: string;
  description: string;
  definition: { nodes: unknown[]; edges: unknown[] };
  warnings: string[];
}

export function importDifyDSL(rawText: string): ImportResult {
  const warnings: string[] = [];

  // Parse YAML or JSON
  let parsed: unknown;
  try {
    parsed = yaml.load(rawText);
  } catch {
    try {
      parsed = JSON.parse(rawText);
    } catch {
      throw new Error('无法解析文件内容，请确认是合法的 Dify YAML 或 JSON 格式');
    }
  }

  const dsl = parsed as DifyDSL;
  const graph: DifyGraph = dsl.workflow?.graph ?? { nodes: [], edges: [] };

  if (!graph.nodes?.length) {
    throw new Error('未在 DSL 中找到节点数据 (workflow.graph.nodes)');
  }

  const nodes = graph.nodes.map((n, i) => {
    const difyType = n.data?.type ?? 'unknown';
    const myType = DIFY_TYPE_MAP[difyType];
    if (!myType) {
      warnings.push(`节点 "${n.data?.title ?? n.id}" (type=${difyType}) 未映射，已转为变量赋值节点`);
    }
    const pos = n.position ?? n.positionAbsolute ?? { x: 100 + i * 200, y: 200 };
    return {
      id: n.id,
      type: myType ?? 'variable',
      position: { x: pos.x, y: pos.y },
      data: convertNodeData(n),
    };
  });

  const edges = (graph.edges ?? []).map((e, i) => ({
    id: e.id ?? `e${i}`,
    source: e.source,
    sourceHandle: e.sourceHandle ?? 'source',
    target: e.target,
    targetHandle: e.targetHandle ?? 'target',
    type: 'default',
  }));

  return {
    name: dsl.app?.name ?? '从 Dify 导入的工作流',
    description: dsl.app?.description ?? '',
    definition: { nodes, edges },
    warnings,
  };
}
