import { useCallback, useRef, type DragEvent } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { nodeTypes } from '@/components/nodes';
import { useWorkflowStore } from '@/stores/workflowStore';

let nodeId = 0;
function getNextId() {
  return `node_${++nodeId}_${Date.now()}`;
}

export default function FlowCanvas() {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const onNodesChange = useWorkflowStore((s) => s.onNodesChange);
  const onEdgesChange = useWorkflowStore((s) => s.onEdgesChange);
  const onConnect = useWorkflowStore((s) => s.onConnect);
  const addNode = useWorkflowStore((s) => s.addNode);
  const selectNode = useWorkflowStore((s) => s.selectNode);

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/agentflow-node-type');
      const dataStr = event.dataTransfer.getData('application/agentflow-node-data');

      if (!type || !reactFlowInstance.current) return;

      const position = reactFlowInstance.current.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const defaultData = dataStr ? JSON.parse(dataStr) : { label: type };
      const newNode = {
        id: getNextId(),
        type,
        position,
        data: defaultData,
      };

      addNode(newNode);
    },
    [addNode]
  );

  return (
    <div ref={reactFlowWrapper} className="flex-1 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={(instance) => { reactFlowInstance.current = instance; }}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={(_, node) => selectNode(node.id)}
        onPaneClick={() => selectNode(null)}
        fitView
        deleteKeyCode={['Backspace', 'Delete']}
        className="bg-gray-50"
      >
        <Controls className="!bg-white !border-gray-200 !shadow-md" />
        <MiniMap
          className="!bg-white !border-gray-200 !shadow-md"
          nodeColor={(node) => {
            const colorMap: Record<string, string> = {
              start: '#22c55e',
              llm: '#8b5cf6',
              tool: '#f59e0b',
              condition: '#06b6d4',
              loop: '#ec4899',
              human: '#14b8a6',
              variable: '#64748b',
              skill: '#a855f7',
              end: '#ef4444',
            };
            return colorMap[node.type || ''] || '#999';
          }}
          maskColor="rgba(0,0,0,0.08)"
        />
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#d1d5db" />
      </ReactFlow>
    </div>
  );
}
