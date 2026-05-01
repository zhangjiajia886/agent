<!-- 高级表单 -->
<template>
  <ElForm
    ref="formRef"
    :model="model"
    :labelPosition="labelPosition"
    :labelWidth="labelWidth"
    :statusIcon="statusIcon"
    :validateOnRuleChange="validateOnRuleChange"
    :size="size"
    :disabled="disabled"
    :scrollToError="scrollToError"
    @submit.prevent=""
  >
    <slot name="topExtra"></slot>
    <ProFormContent
      :model="model"
      :rules="rules"
      :items="items"
      :grid="grid"
      :rowProps="rowProps"
      :contentExtraColProps="footerColProps"
      :searchExpand="searchExpand"
      @updateItemValue="updateValue"
    >
      <template
        v-for="name in Object.keys($slots).filter(
          (k) => !slotExcludes.includes(k)
        )"
        #[name]="slotProps"
      >
        <slot :name="name" v-bind="slotProps || {}"></slot>
      </template>
      <template v-if="footer" #contentExtra>
        <ProFormFooter
          :footerProps="footerProps"
          :footerSlots="footerSlots"
          :footerStyle="footerStyle"
          :submitText="submitText"
          :resetText="resetText"
          :submitButtonProps="submitButtonProps"
          :resetButtonProps="resetButtonProps"
          :showSearchExpand="showSearchExpand"
          :searchExpand="searchExpand"
          :searchExpandButtonProps="searchExpandButtonProps"
          :searchExpandText="searchExpandText"
          :searchShrinkText="searchShrinkText"
          @submit="submit"
          @reset="reset"
          @updateSearchExpand="updateSearchExpand"
        >
          <template
            v-for="name in Object.keys($slots).filter(
              (k) => !fSlotExcludes.includes(k)
            )"
            #[name]="slotProps"
          >
            <slot :name="name" v-bind="slotProps || {}"></slot>
          </template>
        </ProFormFooter>
      </template>
    </ProFormContent>
    <slot name="bottomExtra"></slot>
  </ElForm>
</template>

<script lang="ts" setup>
  import type { CSSProperties } from 'vue';
  import { ref, nextTick } from 'vue';
  import type { FormInstance, FormRules } from 'element-plus';
  import type {
    ElRowProps,
    ElColProps,
    ElFormItemProps,
    ElButtonProps,
    ElLinkProps
  } from 'ele-admin-plus/es/ele-app/el';
  import ProFormContent from './components/pro-form-content.vue';
  import ProFormFooter from './components/pro-form-footer.vue';
  import type { ProFormItemProps } from './types';
  const fSlotExcludes = ['default', 'topExtra', 'bottomExtra', 'contentExtra'];
  const slotExcludes = [...fSlotExcludes, 'footer', 'footerExtra'];

  defineOptions({ name: 'ProForm' });

  const props = withDefaults(
    defineProps<{
      /** 表单数据 */
      model: Record<string, any>;
      /** 验证规则 */
      rules?: FormRules;
      /** 表单域标签的位置 */
      labelPosition?: 'left' | 'right' | 'top';
      /** 标签长度 */
      labelWidth?: string | number;
      /** 是否显示校验结果图标 */
      statusIcon?: boolean;
      /** 是否在rules属性改变后立即触发一次验证 */
      validateOnRuleChange?: boolean;
      /** 尺寸 */
      size?: 'large' | 'default' | 'small';
      /** 是否禁用 */
      disabled?: boolean;
      /** 当校验失败时滚动到第一个错误表单项 */
      scrollToError?: boolean;
      /** 表单项 */
      items: ProFormItemProps[];
      /** 是否栅格布局 */
      grid?: boolean | ElColProps;
      /** ElRow属性 */
      rowProps?: ElRowProps;
      /** 是否需要底栏 */
      footer?: boolean;
      /** 底栏ElFormItem属性 */
      footerProps?: ElFormItemProps;
      /** 底栏ElFormItem插槽 */
      footerSlots?: Record<string, string>;
      /** 底栏ElCol属性 */
      footerColProps?: ElColProps;
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
      /** 展开和收起按钮属性 */
      searchExpandButtonProps?: ElLinkProps;
      /** 展开按钮的文字 */
      searchExpandText?: string;
      /** 收起按钮的文字 */
      searchShrinkText?: string;
    }>(),
    {
      labelWidth: '80px',
      footerColProps: () => {
        return { span: 24 };
      },
      submitText: '提交',
      resetText: '重置',
      searchExpandText: '展开',
      searchShrinkText: '收起'
    }
  );

  const emit = defineEmits<{
    (e: 'updateValue', prop: string, value: unknown): void;
    (e: 'submit', model: Record<string, any>): void;
    (e: 'reset'): void;
  }>();

  /** 搜索表单展开状态 */
  const searchExpand = defineModel('searchExpand', { type: Boolean });

  /** 表单实例 */
  const formRef = ref<FormInstance | null>(null);

  /** 更新值 */
  const updateValue = (prop: string, value: unknown) => {
    emit('updateValue', prop, value);
  };

  /** 更新搜索表单展开状态 */
  const updateSearchExpand = (expand: boolean) => {
    searchExpand.value = expand;
  };

  /** 提交 */
  const submit = () => {
    formRef.value?.validate?.((valid) => {
      if (valid) {
        emit('submit', props.model);
      }
    });
  };

  /** 重置 */
  const reset = () => {
    emit('reset');
    clearValidate();
    nextTick(() => {
      clearValidate();
      nextTick(() => {
        clearValidate();
      });
    });
  };

  /** 验证表单 */
  const validate: FormInstance['validate'] = (callback) => {
    if (!formRef.value) {
      throw new Error('formRef is null');
    }
    return formRef.value.validate(callback);
  };

  /** 验证表单某个字段 */
  const validateField: FormInstance['validateField'] = (props, callback) => {
    if (!formRef.value) {
      throw new Error('formRef is null');
    }
    return formRef.value.validateField(props, callback);
  };

  /** 重置表单 */
  const resetFields: FormInstance['resetFields'] = (props) => {
    if (!formRef.value) {
      throw new Error('formRef is null');
    }
    return formRef.value.resetFields(props);
  };

  /** 滚动到指定字段 */
  const scrollToField: FormInstance['scrollToField'] = (prop) => {
    if (!formRef.value) {
      throw new Error('formRef is null');
    }
    return formRef.value.scrollToField(prop);
  };

  /** 清理表单验证信息 */
  const clearValidate: FormInstance['clearValidate'] = (props) => {
    if (!formRef.value) {
      throw new Error('formRef is null');
    }
    return formRef.value.clearValidate(props);
  };

  defineExpose({
    formRef,
    validate,
    validateField,
    resetFields,
    scrollToField,
    clearValidate
  });
</script>
