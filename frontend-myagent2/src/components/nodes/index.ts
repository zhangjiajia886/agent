import StartNode from './StartNode';
import EndNode from './EndNode';
import LLMNode from './LLMNode';
import ToolNode from './ToolNode';
import ConditionNode from './ConditionNode';
import LoopNode from './LoopNode';
import HumanNode from './HumanNode';
import VariableNode from './VariableNode';
import SkillNode from './SkillNode';

export const nodeTypes = {
  start: StartNode,
  llm: LLMNode,
  tool: ToolNode,
  condition: ConditionNode,
  loop: LoopNode,
  human: HumanNode,
  variable: VariableNode,
  skill: SkillNode,
  end: EndNode,
};
