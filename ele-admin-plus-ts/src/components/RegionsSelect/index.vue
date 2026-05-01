<!-- 省市区级联选择 -->
<template>
  <template v-if="component === 'text'">
    <span v-if="typeof valueLabels === 'string'">{{ valueLabels }}</span>
    <el-space v-else :wrap="true">
      <el-tag
        v-for="label in valueLabels"
        :key="label"
        :disable-transitions="true"
        size="small"
        type="info"
      >
        {{ label }}
      </el-tag>
    </el-space>
  </template>
  <el-cascader
    v-else
    ref="cascaderRef"
    :size="size"
    :disabled="disabled"
    :clearable="clearable"
    v-model="model"
    :options="cascaderData"
    :filterable="filterable"
    :placeholder="placeholder"
    :props="cascaderProps"
    popper-class="ele-popper-higher"
    :collapse-tags="collapseTags"
    :max-collapse-tags="maxCollapseTags"
    :collapse-tags-tooltip="collapseTagsTooltip"
    :teleported="teleported"
    class="ele-fluid"
  />
</template>

<script lang="ts" setup>
  import { ref, computed } from 'vue';
  import type {
    ElCascaderProps,
    ElCascaderInstance
  } from 'ele-admin-plus/es/ele-app/el';
  import type { RegionsData } from './util';
  import { useRegionsData, filterData, getValueLabel } from './util';

  defineOptions({ name: 'RegionsSelect' });

  const props = withDefaults(
    defineProps<{
      /** 自定义省市区数据 */
      options?: RegionsData[];
      /** 选中值对应的字段名 */
      valueField?: 'value' | 'label';
      /** 类型, 省市选择或省选择 */
      type?: 'provinceCity' | 'province';
      /** 组件类型 */
      component?: 'text' | 'cascader';
      /** 级联选择器属性 */
      placeholder?: string;
      disabled?: boolean;
      clearable?: boolean;
      filterable?: boolean;
      cascaderProps?: ElCascaderProps;
      collapseTags?: boolean;
      maxCollapseTags?: number;
      collapseTagsTooltip?: boolean;
      teleported?: boolean;
      size?: 'small' | 'default' | 'large';
    }>(),
    {
      clearable: true,
      filterable: true,
      collapseTags: true,
      maxCollapseTags: 5,
      teleported: true
    }
  );

  /** 选中值 */
  const model = defineModel<string[] | string[][]>({ type: Array });

  /** 省市区数据 */
  const regionsData = useRegionsData();

  /** 级联选择器实例 */
  const cascaderRef = ref<ElCascaderInstance>(null);

  /** 级联选择器数据 */
  const cascaderData = computed<any>(() => {
    const data = props.options ?? regionsData.value ?? [];
    return filterData(data, props.type, props.valueField);
  });

  /** 选中值对应的文本 */
  const valueLabels = computed<string | string[]>(() => {
    const separator = ' / ';
    const values = model.value;
    if (values && values.length && Array.isArray(values[0])) {
      const result: string[] = [];
      (values as Array<string[]>).forEach((v) => {
        const labels = getValueLabel(v, cascaderData.value);
        result.push(labels.join(separator));
      });
      return result;
    }
    const labels = getValueLabel(values as string[], cascaderData.value);
    return labels.join(separator);
  });

  defineExpose({
    cascaderRef,
    getCheckedNodes: (leafOnly?: boolean) => {
      return cascaderRef.value?.getCheckedNodes?.(!!leafOnly);
    }
  });
</script>
