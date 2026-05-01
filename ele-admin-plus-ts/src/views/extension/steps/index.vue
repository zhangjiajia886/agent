<template>
  <ele-page>
    <ele-card header="基础用法">
      <ele-steps
        :active="active"
        finish-status="success"
        :items="[
          { title: '第一步', description: '填写转账信息' },
          { title: '第二步', description: '确认转账信息' },
          { title: '第三步', description: '转账成功' }
        ]"
        :align-center="!!alignCenter"
      />
      <div style="margin-top: 28px; display: flex; align-items: center">
        <el-button @click="handlePrev">上一步</el-button>
        <el-button type="primary" @click="handleNext">下一步</el-button>
        <div style="margin-left: 12px">
          <el-checkbox
            v-model="alignCenter"
            :true-value="1"
            :false-value="0"
            label="居中"
          />
        </div>
      </div>
    </ele-card>
    <ele-card header="紧凑版">
      <ele-steps
        :active="active"
        finish-status="success"
        type="inline"
        :items="[
          { title: '第一步', description: '填写转账信息' },
          { title: '第二步', description: '确认转账信息' },
          { title: '第三步', description: '转账成功' }
        ]"
      />
    </ele-card>
    <ele-card header="竖直方向">
      <div style="height: 320px">
        <ele-steps
          :active="active"
          finish-status="success"
          direction="vertical"
          :items="[
            { title: '第一步', description: '填写转账信息' },
            { title: '第二步', description: '确认转账信息' },
            { title: '第三步', description: '转账成功' }
          ]"
        />
      </div>
    </ele-card>
    <ele-card header="带图标紧凑版">
      <div style="margin-bottom: 28px">
        <el-button @click="handlePrev">上一步</el-button>
        <el-button type="primary" @click="handleNext">下一步</el-button>
      </div>
      <ele-steps
        :active="active"
        type="inline"
        :items="[
          { title: '账号注册', icon: UserFilled },
          { title: '邮箱验证', icon: Checked },
          { title: '注册完成', icon: SuccessFilled }
        ]"
        :style="{
          '--ele-step-icon-size': '24px',
          '--ele-step-line-height': '24px'
        }"
      />
    </ele-card>
    <ele-card header="带图标居中版">
      <ele-steps
        :active="active"
        :align-center="true"
        :items="[
          { title: '账号注册', icon: UserFilled },
          { title: '邮箱验证', icon: Checked },
          { title: '注册完成', icon: SuccessFilled }
        ]"
        :style="{
          '--ele-step-icon-size': '24px',
          '--ele-step-line-height': '24px'
        }"
      />
    </ele-card>
  </ele-page>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import { UserFilled, Checked, SuccessFilled } from '@element-plus/icons-vue';

  defineOptions({ name: 'ExtensionSteps' });

  /** 选中步骤 */
  const active = ref(0);

  /** 居中 */
  const alignCenter = ref(0);

  /** 上一步 */
  const handlePrev = () => {
    if (active.value < 1) {
      active.value = 3;
      return;
    }
    active.value = active.value - 1;
  };

  /** 下一步 */
  const handleNext = () => {
    if (active.value > 2) {
      active.value = 0;
      return;
    }
    active.value = active.value + 1;
  };
</script>
