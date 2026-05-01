<template>
  <CommonUpload
    v-model="files"
    :fileLimit="fileLimit"
    :readonly="readonly"
    :disabled="disabled"
    :preview="preview"
    :limit="limit"
    :multiple="multiple"
    :drag="drag"
    :accept="accept"
    :itemStyle="itemStyle"
    :buttonStyle="buttonStyle"
    :sortable="sortable"
    :imageProps="imageProps"
    :progressProps="progressProps"
    :previewProps="previewProps"
    :tools="tools"
    :listType="listType"
    :beforeUploadClick="beforeUploadClick"
    :beforeItemEdit="beforeItemEdit"
    :locale="locale"
    @itemClick="handleItemClick"
    @preview="handleItemPreview"
  />
</template>

<script lang="ts" setup>
  import type { CSSProperties } from 'vue';
  import { ref, watch } from 'vue';
  import type {
    ElProgressProps,
    ElImageProps
  } from 'ele-admin-plus/es/ele-app/el';
  import type { EleImageViewerProps } from 'ele-admin-plus/es/ele-app/plus';
  import type {
    UploadItem,
    ListType,
    BeforeUploadClick,
    BeforeItemEdit,
    UploadLocale
  } from 'ele-admin-plus/es/ele-upload-list/types';
  import CommonUpload from '../CommonUpload/index.vue';

  defineOptions({ name: 'FileUpload' });

  const props = withDefaults(
    defineProps<{
      /** 绑定值 */
      modelValue?: string;
      /** 文件大小限制, 单位MB */
      fileLimit?: number;
      /** 是否只读 */
      readonly?: boolean;
      /** 是否禁用 */
      disabled?: boolean;
      /** 是否支持点击预览 */
      preview?: boolean;
      /** 最大上传数量 */
      limit?: number;
      /** 是否支持多选文件 */
      multiple?: boolean;
      /** 是否启用拖拽上传 */
      drag?: boolean;
      /** 接受上传的文件类型 */
      accept?: string;
      /** 自定义样式 */
      itemStyle?: CSSProperties;
      /** 自定义上传按钮样式 */
      buttonStyle?: CSSProperties;
      /** 是否开启拖拽排序 */
      sortable?: boolean | Record<keyof any, any>;
      /** 自定义图片属性 */
      imageProps?: ElImageProps;
      /** 自定义进度条属性 */
      progressProps?: ElProgressProps;
      /** 自定义图片预览属性 */
      previewProps?: EleImageViewerProps;
      /** 是否开启底部预览和修改的操作按钮 */
      tools?: boolean;
      /** 列表显示样式 */
      listType?: ListType;
      /** 上传按钮点击前的钩子 */
      beforeUploadClick?: BeforeUploadClick;
      /** 修改按钮点击前的钩子 */
      beforeItemEdit?: BeforeItemEdit;
      /** 国际化 */
      locale?: Partial<UploadLocale>;
    }>(),
    {
      fileLimit: 100,
      preview: true,
      drag: true,
      accept: '',
      sortable: () => ({ forceFallback: true }),
      tools: true,
      listType: 'file'
    }
  );

  const emit = defineEmits<{
    (e: 'update:modelValue', value?: string): void;
    (e: 'change', value?: string): void;
  }>();

  /** 绑定值数据类型 */
  interface DataValueItem {
    url: string;
    name?: string;
  }

  /** 上传组件数据 */
  const files = ref<UploadItem[]>([]);

  /** 判断是否是图片 */
  const isImage = (url?: string) => {
    const parts = url ? url.split('.') : [];
    const suffix =
      parts.length <= 1 || (parts[0] === '' && parts.length === 2)
        ? ''
        : parts.pop()?.toLowerCase?.();
    return suffix && ['png', 'jpg', 'jpeg', 'gif', 'svg'].includes(suffix);
  };

  /** 获取上传组件数据的地址 */
  const getItemFileUrl = (item: UploadItem): string => {
    return item.fileUrl;
  };

  /** 点击事件 */
  const handleItemClick = (item: UploadItem) => {
    handleItemPreview(item);
  };

  /** 预览事件 */
  const handleItemPreview = (item: UploadItem) => {
    if (!item.url) {
      const fileUrl = getItemFileUrl(item);
      if (fileUrl) {
        window.open(fileUrl);
      } else if (item.file && !item.file.type.startsWith('image')) {
        window.open(URL.createObjectURL(item.file));
      }
    }
  };

  /** 更新绑定值 */
  const updateModelValue = (value: string) => {
    if (props.modelValue !== value) {
      emit('update:modelValue', value);
      emit('change', value);
    }
  };

  /** 清空上传组件数据 */
  const clearData = () => {
    files.value = [];
  };

  /** 判断是否全部上传完成 */
  const isDone = () => {
    return !files.value.some((d) => d.status !== 'done');
  };

  /** 获取上传数据对应的值 */
  const getDataValue = (filesValue: UploadItem[]) => {
    const result: DataValueItem[] = [];
    filesValue.forEach((item) => {
      const fileUrl = getItemFileUrl(item);
      if (item.status === 'done' && fileUrl != null) {
        result.push({ url: fileUrl, name: item.name });
      }
    });
    return result;
  };

  /** 获取值对应的上传数据 */
  const getFilesValue = (
    dataValue: string | undefined | null,
    filesValue: UploadItem[]
  ) => {
    if (!dataValue) {
      return filesValue.filter((item) => item.status !== 'done');
    }
    const result: UploadItem[] = [];
    if (props.limit === 1) {
      try {
        const temp = JSON.parse(dataValue);
        if (temp) {
          const url = temp.url ?? '';
          result.push({
            key: `0-${url}`,
            name: temp.name ?? '',
            url: isImage(url) ? url : void 0,
            fileUrl: url,
            status: 'done'
          });
          return result;
        }
      } catch (e) {
        console.error(e);
      }
      const temp = filesValue.find((item) => item.status !== 'done');
      if (temp != null) {
        result.push(temp);
      }
      return result;
    }
    try {
      const temps: DataValueItem[] = JSON.parse(dataValue);
      filesValue.forEach((item) => {
        const fileUrl = getItemFileUrl(item);
        if (
          (fileUrl && temps.some((temp) => temp.url === fileUrl)) ||
          item.status !== 'done'
        ) {
          result.push(item);
        }
      });
      temps.forEach((temp, index) => {
        const url = temp?.url ?? '';
        if (url && !result.some((item) => getItemFileUrl(item) === url)) {
          const key = `${index}-${url}`;
          const oldIndex = result.findIndex((item) => item.key === key);
          if (oldIndex !== -1) {
            result.splice(oldIndex, 1);
          }
          result.push({
            key,
            name: temp.name ?? '',
            url: isImage(url) ? url : void 0,
            fileUrl: url,
            status: 'done'
          });
        }
      });
      if (props.limit != null && result.length > props.limit) {
        const temp = result.filter((item) => item.status !== 'done');
        for (const t of temp) {
          const i = result.indexOf(t);
          result.splice(i, 1);
          if (result.length <= props.limit) {
            break;
          }
        }
      }
    } catch (e) {
      console.error(e);
      filesValue.forEach((item) => {
        if (item.status !== 'done') {
          result.push(item);
        }
      });
    }
    return result;
  };

  /** 判断上传数据是否改变 */
  const filesIsChanged = (newFiles: UploadItem[], oldFiles: UploadItem[]) => {
    if (newFiles.length !== oldFiles.length) {
      return true;
    }
    for (let i = 0; i < newFiles.length; i++) {
      const newItem = newFiles[i];
      const oldItem = oldFiles[i];
      if (
        newItem.key !== oldItem.key ||
        newItem.name !== oldItem.name ||
        getItemFileUrl(newItem) !== getItemFileUrl(oldItem) ||
        newItem.status !== oldItem.status
      ) {
        return true;
      }
    }
    return false;
  };

  /** 同步绑定值 */
  watch(
    files,
    (filesValue) => {
      const dataValue = getDataValue(filesValue);
      if (props.limit === 1) {
        updateModelValue(dataValue.length ? JSON.stringify(dataValue[0]) : '');
        return;
      }
      updateModelValue(dataValue.length ? JSON.stringify(dataValue) : '');
    },
    { deep: true }
  );

  watch(
    () => props.modelValue,
    (dataValue) => {
      const filesValue = getFilesValue(dataValue, files.value);
      if (filesIsChanged(filesValue, files.value)) {
        files.value = filesValue;
      }
    },
    { immediate: true }
  );

  defineExpose({ clearData, isDone });
</script>
