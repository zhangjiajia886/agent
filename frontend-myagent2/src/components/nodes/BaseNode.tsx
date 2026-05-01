import { Handle, Position } from '@xyflow/react';
import type { ReactNode } from 'react';

interface BaseNodeProps {
  label: string;
  icon: ReactNode;
  color: string;
  selected?: boolean;
  children?: ReactNode;
  handles?: {
    // left = input (target), right = output (source) — primary for horizontal flow
    left?: boolean;
    right?: boolean;
    // top/bottom kept for back-compat (map to left/right)
    top?: boolean;
    bottom?: boolean;
    extraOutputs?: Array<{ id: string; label: string; topPercent: number }>;
  };
}

export default function BaseNode({
  label,
  icon,
  color,
  selected,
  children,
  handles = { left: true, right: true },
}: BaseNodeProps) {
  // Normalise: top/bottom aliases for left/right
  const showLeft  = handles.left  ?? handles.top  ?? false;
  const showRight = handles.right ?? handles.bottom ?? false;
  return (
    <div
      className={`
        bg-white rounded-xl shadow-md border-2 min-w-[180px] max-w-[260px]
        transition-all duration-150
        ${selected ? 'shadow-lg ring-2 ring-blue-400' : 'hover:shadow-lg'}
      `}
      style={{ borderColor: selected ? '#3b82f6' : color }}
    >
      {/* 标题栏 */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-t-lg text-white text-sm font-medium"
        style={{ backgroundColor: color }}
      >
        {icon}
        <span className="truncate">{label}</span>
      </div>

      {/* 内容区 */}
      {children && (
        <div className="px-3 py-2 text-xs text-gray-600">{children}</div>
      )}

      {/* Handles — horizontal flow: Left = input, Right = output */}
      {showLeft && (
        <Handle
          type="target"
          position={Position.Left}
          id="target"
          className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
        />
      )}
      {showRight && (
        <Handle
          type="source"
          position={Position.Right}
          id="source"
          className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
        />
      )}
      {handles.extraOutputs?.map((output) => (
        <Handle
          key={output.id}
          type="source"
          position={Position.Right}
          id={output.id}
          className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
          style={{ top: `${output.topPercent}%` }}
        />
      ))}
    </div>
  );
}
