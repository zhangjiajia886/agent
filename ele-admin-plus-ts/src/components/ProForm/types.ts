import type {
  ElFormItemProps,
  ElRowProps,
  ElColProps
} from 'ele-admin-plus/es/ele-app/el';

/**
 * 下拉选项数据
 */
export interface ProFormItemOption {
  /** 循环的key */
  key?: keyof any;
  /** 选中值 */
  value: string | number;
  /** 显示文本 */
  label?: string;
  /** 子级 */
  children?: ProFormItemOption[];
  /** 是否禁用 */
  disabled?: boolean;
}

/**
 * 表单每一项
 */
export interface ProFormItemProps {
  /** 循环key */
  key?: keyof any;
  /** 字段名 */
  prop: string;
  /** 标题 */
  label?: string;
  /** 是否为必填项 */
  required?: boolean;
  /** ElFormItem属性 */
  itemProps?: ElFormItemProps;
  /** ElFormItem插槽 */
  itemSlots?: Record<string, string>;
  /** 组件类型 */
  type?: string;
  /** 组件属性 */
  props?: Record<string, any>;
  /** 组件插槽 */
  slots?: Record<string, string>;
  /** 下拉[单选|多选]选项 */
  options?: ProFormItemOption[];
  /** ElCol属性 */
  colProps?: ElColProps;
  /** 容器组件是否栅格布局 */
  grid?: boolean | ElColProps;
  /** 容器组件栅格布局ElRow属性 */
  rowProps?: ElRowProps;
  /** 自定义组件类型时标识表单项类型 */
  itemType?: 'default' | 'view' | 'container';
  /** 子级 */
  children?: ProFormItemProps[];
  /** 显示条件 */
  vIf?: any;
}
