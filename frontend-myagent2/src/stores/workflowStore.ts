import { create } from 'zustand';
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from '@xyflow/react';
import type { FlowNode, FlowEdge, BaseNodeData } from '@/types/workflow';
import { workflowApi } from '@/api/workflows';

interface WorkflowState {
  // 持久化 ID (null = 尚未保存)
  workflowId: string | null;
  dirty: boolean;
  saving: boolean;
  loading: boolean;

  // 画布数据
  nodes: FlowNode[];
  edges: FlowEdge[];
  // 选中状态
  selectedNodeId: string | null;
  // 工作流元信息
  workflowName: string;
  workflowDescription: string;

  // React Flow 回调
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;

  // 操作方法
  setNodes: (nodes: FlowNode[]) => void;
  setEdges: (edges: FlowEdge[]) => void;
  addNode: (node: FlowNode) => void;
  updateNodeData: (nodeId: string, data: Partial<BaseNodeData>) => void;
  deleteNode: (nodeId: string) => void;
  selectNode: (nodeId: string | null) => void;
  getSelectedNode: () => FlowNode | undefined;

  // 持久化方法
  setWorkflowMeta: (name: string, description: string) => void;
  resetForNew: () => void;
  loadWorkflow: (id: string) => Promise<void>;
  saveWorkflow: () => Promise<string>;
}

const EMPTY_START: FlowNode[] = [
  { id: 'start_1', type: 'start', position: { x: 300, y: 40 }, data: { label: '开始', outputs: ['user_query'] } },
  { id: 'end_1', type: 'end', position: { x: 300, y: 300 }, data: { label: '结束', outputs: ['result'] } },
];
const EMPTY_EDGES: FlowEdge[] = [
  { id: 'e_init', source: 'start_1', target: 'end_1', animated: true },
];

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflowId: null,
  dirty: false,
  saving: false,
  loading: false,

  nodes: EMPTY_START,
  edges: EMPTY_EDGES,
  selectedNodeId: null,
  workflowName: '新建工作流',
  workflowDescription: '',

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes) as FlowNode[], dirty: true });
  },

  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges), dirty: true });
  },

  onConnect: (connection) => {
    set({ edges: addEdge({ ...connection, animated: true }, get().edges), dirty: true });
  },

  setNodes: (nodes) => set({ nodes, dirty: true }),
  setEdges: (edges) => set({ edges, dirty: true }),

  addNode: (node) => {
    set({ nodes: [...get().nodes, node], dirty: true });
  },

  updateNodeData: (nodeId, data) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      ),
      dirty: true,
    });
  },

  deleteNode: (nodeId) => {
    set({
      nodes: get().nodes.filter((n) => n.id !== nodeId),
      edges: get().edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId
      ),
      selectedNodeId:
        get().selectedNodeId === nodeId ? null : get().selectedNodeId,
      dirty: true,
    });
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  getSelectedNode: () => {
    const { nodes, selectedNodeId } = get();
    return nodes.find((n) => n.id === selectedNodeId);
  },

  setWorkflowMeta: (name, description) => set({ workflowName: name, workflowDescription: description, dirty: true }),

  resetForNew: () => set({
    workflowId: null,
    nodes: [...EMPTY_START],
    edges: [...EMPTY_EDGES],
    selectedNodeId: null,
    workflowName: '新建工作流',
    workflowDescription: '',
    dirty: false,
    saving: false,
    loading: false,
  }),

  loadWorkflow: async (id: string) => {
    set({ loading: true });
    try {
      const wf = await workflowApi.get(id);
      const def = wf.definition as { nodes?: FlowNode[]; edges?: FlowEdge[] };
      set({
        workflowId: wf.id,
        workflowName: wf.name,
        workflowDescription: wf.description,
        nodes: def.nodes || [...EMPTY_START],
        edges: def.edges || [...EMPTY_EDGES],
        selectedNodeId: null,
        dirty: false,
      });
    } finally {
      set({ loading: false });
    }
  },

  saveWorkflow: async () => {
    const { workflowId, workflowName, workflowDescription, nodes, edges } = get();
    const definition = { nodes, edges };
    set({ saving: true });
    try {
      if (workflowId) {
        await workflowApi.update(workflowId, { name: workflowName, description: workflowDescription, definition });
        set({ dirty: false });
        return workflowId;
      } else {
        const res = await workflowApi.create({ name: workflowName, description: workflowDescription, definition });
        set({ workflowId: res.id, dirty: false });
        return res.id;
      }
    } finally {
      set({ saving: false });
    }
  },
}));
