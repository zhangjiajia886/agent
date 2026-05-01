<template>
  <ElFormItem v-bind="footerProps || {}">
    <template
      v-for="name in Object.keys(footerSlots || {}).filter(
        (k) =>
          k !== 'footer' &&
          !!(footerSlots && footerSlots[k] && $slots[footerSlots[k]])
      )"
      #[name]="slotProps"
    >
      <slot :name="footerSlots?.[name]" v-bind="slotProps || {}"></slot>
    </template>
    <div
      :style="{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        ...(footerStyle || {})
      }"
    >
      <slot name="footer">
        <ElButton
          type="primary"
          v-bind="submitButtonProps || {}"
          @click="submit"
        >
          {{ submitText }}
        </ElButton>
        <ElButton v-bind="resetButtonProps || {}" @click="reset">
          {{ resetText }}
        </ElButton>
      </slot>
      <ElLink
        v-if="showSearchExpand"
        type="primary"
        :underline="false"
        style="margin-left: 12px"
        v-bind="searchExpandButtonProps || {}"
        @click="toggleSearchExpand"
      >
        <template v-if="searchExpand">
          <span>{{ searchShrinkText }}</span>
          <ElIcon style="vertical-align: -1px">
            <ArrowUp />
          </ElIcon>
        </template>
        <template v-else>
          <span>{{ searchExpandText }}</span>
          <ElIcon style="vertical-align: -2px">
            <ArrowDown />
          </ElIcon>
        </template>
      </ElLink>
      <slot name="footerExtra"></slot>
    </div>
  </ElFormItem>
</template>

<script lang="ts" setup>
  import type { CSSProperties } from 'vue';
  import type {
    ElFormItemProps,
    ElButtonProps,
    ElLinkProps
  } from 'ele-admin-plus/es/ele-app/el';
  import { ArrowDown, ArrowUp } from '@/components/icons';

  const props = defineProps<{
    /** 底栏ElFormItem属性 */
    footerProps?: ElFormItemProps;
    /** 底栏ElFormItem插槽 */
    footerSlots?: Record<string, string>;
    /** 底栏样式 */
    footerStyle?: CSSProperties;
    /** 提交按钮文本 */
    submitText?: string;
    /** 重置按钮文本 */
    resetText?: string;
    /** 提交按钮属性 */
    submitButtonProps?: ElButtonProps;
    /** 重置按钮属性 */
    resetButtonProps?: ElButtonProps;
    /** 是否在底栏显示表单展开收起按钮 */
    showSearchExpand?: boolean;
    /** 搜索表单展开状态 */
    searchExpand?: boolean;
    /** 展开和收起按钮属性 */
    searchExpandButtonProps?: ElLinkProps;
    /** 展开按钮的文字 */
    searchExpandText?: string;
    /** 收起按钮的文字 */
    searchShrinkText?: string;
  }>();

  const emit = defineEmits<{
    (e: 'submit'): void;
    (e: 'reset'): void;
    (e: 'updateSearchExpand', expand: boolean): void;
  }>();

  /** 提交 */
  const submit = () => {
    emit('submit');
  };

  /** 重置 */
  const reset = () => {
    emit('reset');
  };

  /** 切换搜索表单展开状态 */
  const toggleSearchExpand = () => {
    emit('updateSearchExpand', !props.searchExpand);
  };
</script>
