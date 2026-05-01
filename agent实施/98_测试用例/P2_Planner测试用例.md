# P2 Planner 测试用例

## 用例 1：单图生成

- **输入**：生成一张仙侠图
- **期望 TaskGraph**：
  - [ ] 1 个 required step
  - [ ] tool_name 为 generate_image 或可用 fallback
  - [ ] output_artifact_types 包含 image

## 用例 2：图片转视频

- **输入**：生成一张图并让它动起来
- **期望 TaskGraph**：
  - [ ] s1 generate_image
  - [ ] s2 image_to_video depends_on s1

## 用例 3：视频配旁白合成

- **输入**：生成图片，转视频，配旁白，合成为完整视频
- **期望 TaskGraph**：
  - [ ] generate_image
  - [ ] image_to_video depends_on image
  - [ ] text_to_speech
  - [ ] merge_media depends_on video/audio

## 用例 4：四格漫剧

- **输入**：生成四格仙侠漫剧
- **参数**：frames=4
- **期望 TaskGraph**：
  - [ ] storyboard 或 planning step
  - [ ] 4 个 frame image steps
  - [ ] merge_comic depends_on 4 个图片步骤

## 用例 5：缺工具

- **模拟方式**：禁用 image_to_video
- **期望**：
  - [ ] step blocked 或 fallback_tools 不为空
  - [ ] 不生成不可执行计划
