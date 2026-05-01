import { NODE_TEMPLATES, NODE_CATEGORIES } from '@/constants/nodeTemplates';
import {
  Play, Bot, Wrench, GitBranch, RefreshCw,
  UserCheck, Variable, Square, BrainCircuit,
} from 'lucide-react';
import type { DragEvent } from 'react';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number }>> = {
  Play, Bot, Wrench, GitBranch, RefreshCw,
  UserCheck, Variable, Square, BrainCircuit,
};

function onDragStart(event: DragEvent, nodeType: string, defaultData: object) {
  event.dataTransfer.setData('application/agentflow-node-type', nodeType);
  event.dataTransfer.setData('application/agentflow-node-data', JSON.stringify(defaultData));
  event.dataTransfer.effectAllowed = 'move';
}

export default function NodeLibrary() {
  return (
    <div className="w-56 bg-gray-50 border-r border-gray-200 flex flex-col h-full overflow-y-auto">
      <div className="px-4 py-3 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-700">节点库</h2>
      </div>

      {NODE_CATEGORIES.map((cat) => {
        const templates = NODE_TEMPLATES.filter((t) => t.category === cat.key);
        if (templates.length === 0) return null;
        return (
          <div key={cat.key} className="px-3 py-2">
            <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-2 px-1">
              {cat.label}
            </div>
            <div className="space-y-1">
              {templates.map((tpl) => {
                const Icon = ICON_MAP[tpl.icon];
                return (
                  <div
                    key={tpl.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, tpl.type, tpl.defaultData)}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-grab
                               hover:bg-white hover:shadow-sm border border-transparent
                               hover:border-gray-200 transition-all duration-100 active:cursor-grabbing"
                  >
                    <div
                      className="w-7 h-7 rounded-md flex items-center justify-center text-white shrink-0"
                      style={{ backgroundColor: tpl.color }}
                    >
                      {Icon && <Icon size={14} />}
                    </div>
                    <span className="text-sm text-gray-700">{tpl.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
