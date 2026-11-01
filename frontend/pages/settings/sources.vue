<template>
  <view :class="['page settings-page sources-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="settings-nav">
      <button class="back-button" @click="goBack" aria-label="返回">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view class="settings-head">
      <view class="source-seal">
        <text class="seal-mark">源</text>
        <text class="seal-check">✓</text>
      </view>
      <view class="head-copy">
        <text class="head-kicker">来源透明度</text>
        <text class="page-title">{{ page.title || '内容来源说明' }}</text>
        <text class="subtle">{{ page.subtitle || '见闻如何选择、整理和呈现公共信息' }}</text>
      </view>
    </view>

    <view class="flow-card card">
      <text class="block-kicker">我们如何使用来源</text>
      <view class="flow-list">
        <view v-for="step in sourceFlow" :key="step.title" class="flow-step">
          <view class="step-index">
            <text>{{ step.index }}</text>
          </view>
          <view class="step-copy">
            <text class="step-title">{{ step.title }}</text>
            <text class="step-desc">{{ step.desc }}</text>
          </view>
        </view>
      </view>
    </view>

    <view class="levels-section">
      <text class="section-heading">来源等级</text>
      <view v-for="level in sourceLevels" :key="level.grade" :class="['source-level-card', level.tone]">
        <view class="level-band">
          <text>{{ level.grade }}</text>
        </view>
        <view class="level-copy">
          <view class="level-title-row">
            <text class="level-name">{{ level.name }}</text>
            <text class="level-tag">{{ level.tag }}</text>
          </view>
          <text class="level-desc">{{ level.desc }}</text>
        </view>
      </view>
    </view>

    <view class="document-section">
      <text class="section-heading">说明正文</text>
      <view v-for="section in page.sections" :key="section.title" class="content-card card">
        <text class="content-title">{{ section.title }}</text>
        <text v-if="section.body" class="content-body">{{ section.body }}</text>
        <view v-for="item in section.items || []" :key="item.title" class="level-item">
          <text class="level-title">{{ item.title }}</text>
          <text class="content-body">{{ item.desc }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { getContentPage } from '@/utils/api.js'

export default {
  data() {
    return {
      darkMode: false,
      fontSize: 'standard',
      sourceFlow: [
        { index: '01', title: '先看出处', desc: '确认信息来自官方文件、机构发布、权威媒体还是平台整理。' },
        { index: '02', title: '再做整理', desc: '把公开信息压缩成摘要、问答和阅读入口，保留可核对线索。' },
        { index: '03', title: '最后核对', desc: '涉及办理、权益和专业判断时，以原始公开来源为准。' }
      ],
      sourceLevels: [
        { grade: 'A', name: '官方来源', tag: '优先采用', tone: 'official', desc: '政府官网、主管部门、公共机构、政务服务平台和正式政策文件。' },
        { grade: 'B', name: '权威媒体', tag: '辅助理解', tone: 'media', desc: '新华社、人民网等公开报道，用于补充背景、时序和社会影响。' },
        { grade: 'C', name: '整理内容', tag: '需再核对', tone: 'assist', desc: '见闻与 AI 辅助生成的摘要、解释和问答草稿，不作为最终依据。' }
      ],
      page: { title: '', subtitle: '', sections: [] }
    }
  },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadPage()
  },
  methods: {
    async loadPage() {
      try {
        this.page = await getContentPage('sources')
      } catch (error) {
        uni.showToast({ title: error.message || '页面内容加载失败', icon: 'none' })
      }
    },
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
        return
      }
      uni.switchTab({ url: '/pages/profile/profile' })
    }
  }
}
</script>

<style scoped>
.sources-page {
  padding-bottom: calc(118rpx + constant(safe-area-inset-bottom));
  padding-bottom: calc(118rpx + env(safe-area-inset-bottom));
}

.settings-nav {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 56rpx;
  margin-bottom: 34rpx;
}

.settings-head,
.head-copy,
.flow-card,
.flow-list,
.flow-step,
.step-copy,
.levels-section,
.source-level-card,
.level-copy,
.content-card,
.level-item {
  display: flex;
  flex-direction: column;
}

.settings-head {
  flex-direction: row;
  align-items: center;
  gap: 28rpx;
  min-height: 206rpx;
  margin-bottom: 36rpx;
}

.source-seal {
  position: relative;
  z-index: 1;
  flex: 0 0 104rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 104rpx;
  height: 104rpx;
  border: 1rpx solid rgba(31, 95, 122, 0.16);
  border-radius: 30rpx;
  background:
    linear-gradient(135deg, rgba(31, 95, 122, 0.12), rgba(212, 170, 78, 0.1)),
    rgba(255, 255, 255, 0.62);
}

.seal-mark {
  color: #1F5F7A;
  font-size: 46rpx;
  font-weight: 900;
  line-height: 1;
}

.seal-check {
  position: absolute;
  right: -6rpx;
  bottom: -6rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38rpx;
  height: 38rpx;
  border: 3rpx solid rgba(255, 255, 255, 0.9);
  border-radius: 999rpx;
  background: #1F5F7A;
  color: #FFFFFF;
  font-size: 21rpx;
  font-weight: 900;
}

.head-copy {
  position: relative;
  z-index: 1;
  flex: 1;
  gap: 12rpx;
  min-width: 0;
}

.head-kicker,
.block-kicker {
  color: #1F5F7A;
  font-size: 23rpx;
  line-height: 1.35;
  font-weight: 900;
}

.flow-card {
  gap: 30rpx;
  margin-bottom: 46rpx;
  padding: 38rpx;
}

.flow-list {
  gap: 26rpx;
}

.flow-step {
  position: relative;
  flex-direction: row;
  gap: 22rpx;
}

.flow-step:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 24rpx;
  top: 58rpx;
  bottom: -16rpx;
  width: 1rpx;
  background: rgba(31, 95, 122, 0.16);
}

.step-index {
  position: relative;
  z-index: 1;
  flex: 0 0 50rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 50rpx;
  height: 50rpx;
  border-radius: 999rpx;
  background: #EAF3F6;
  color: #1F5F7A;
  font-size: 19rpx;
  font-weight: 900;
}

.step-copy {
  flex: 1;
  gap: 8rpx;
  min-width: 0;
}

.step-title {
  color: #14212B;
  font-size: 28rpx;
  line-height: 1.35;
  font-weight: 900;
}

.step-desc {
  color: #5C6873;
  font-size: 25rpx;
  line-height: 1.62;
}

.levels-section,
.document-section {
  margin-bottom: 42rpx;
}

.section-heading {
  display: block;
  margin: 0 0 24rpx;
  color: #14212B;
  font-size: 32rpx;
  line-height: 1.35;
  font-weight: 900;
}

.source-level-card {
  position: relative;
  flex-direction: row;
  gap: 24rpx;
  min-height: 154rpx;
  margin-bottom: 22rpx;
  padding: 28rpx 30rpx 28rpx 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.88);
  border-radius: 28rpx;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 20rpx 50rpx rgba(31, 47, 58, 0.08);
}

.source-level-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8rpx;
}

.source-level-card.official::before {
  background: #1F5F7A;
}

.source-level-card.media::before {
  background: #D4AA4E;
}

.source-level-card.assist::before {
  background: #7BA494;
}

.level-band {
  flex: 0 0 72rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72rpx;
  height: 72rpx;
  border-radius: 24rpx;
  background: rgba(31, 95, 122, 0.1);
  color: #1F5F7A;
  font-size: 38rpx;
  line-height: 1;
  font-weight: 900;
}

.source-level-card.media .level-band {
  background: rgba(212, 170, 78, 0.16);
  color: #9A7423;
}

.source-level-card.assist .level-band {
  background: rgba(123, 164, 148, 0.16);
  color: #426F62;
}

.level-copy {
  flex: 1;
  gap: 14rpx;
  min-width: 0;
}

.level-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.level-name {
  color: #14212B;
  font-size: 30rpx;
  line-height: 1.35;
  font-weight: 900;
}

.level-tag {
  flex: 0 0 auto;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(31, 95, 122, 0.1);
  color: #1F5F7A;
  font-size: 21rpx;
  line-height: 1.2;
  font-weight: 900;
}

.source-level-card.media .level-tag {
  background: rgba(212, 170, 78, 0.16);
  color: #8D6A20;
}

.source-level-card.assist .level-tag {
  background: rgba(123, 164, 148, 0.16);
  color: #426F62;
}

.level-desc {
  color: #52616A;
  font-size: 25rpx;
  line-height: 1.62;
}

.content-card {
  gap: 24rpx;
  margin-bottom: 24rpx;
  padding: 42rpx;
}

.content-title {
  color: #14212B;
  font-size: 34rpx;
  font-weight: 900;
}

.content-body {
  color: #3F4F59;
  font-size: 30rpx;
  line-height: 1.78;
}

.level-item {
  gap: 18rpx;
  padding-top: 30rpx;
  border-top: 1rpx solid #E8EEF2;
}

.level-title {
  color: #1F5F7A;
  font-size: 27rpx;
  font-weight: 900;
}

.font-large .content-body {
  font-size: 33rpx;
}

.font-large .level-desc,
.font-large .step-desc {
  font-size: 28rpx;
}

.font-small .content-body {
  font-size: 27rpx;
}

.font-small .level-desc,
.font-small .step-desc {
  font-size: 23rpx;
}

.dark-mode .source-seal {
  border-color: rgba(126, 184, 209, 0.16);
  background:
    linear-gradient(135deg, rgba(126, 184, 209, 0.12), rgba(187, 141, 45, 0.08)),
    rgba(23, 35, 49, 0.76);
}

.dark-mode .seal-mark,
.dark-mode .head-kicker,
.dark-mode .block-kicker,
.dark-mode .level-title {
  color: #7EB8D1;
}

.dark-mode .seal-check {
  border-color: #172331;
  background: #7EB8D1;
  color: #0E1720;
}

.dark-mode .step-index,
.dark-mode .level-band {
  background: #20384A;
  color: #7EB8D1;
}

.dark-mode .flow-step:not(:last-child)::after {
  background: rgba(126, 184, 209, 0.16);
}

.dark-mode .step-title,
.dark-mode .section-heading,
.dark-mode .level-name {
  color: #F4F7FA;
}

.dark-mode .step-desc,
.dark-mode .level-desc {
  color: #B6C2CC;
}

.dark-mode .source-level-card {
  border-color: rgba(126, 184, 209, 0.16);
  background: rgba(23, 35, 49, 0.86);
  box-shadow: 0 24rpx 60rpx rgba(0, 0, 0, 0.22);
}

.dark-mode .source-level-card.media .level-band,
.dark-mode .source-level-card.media .level-tag {
  background: rgba(187, 141, 45, 0.18);
  color: #D4AA4E;
}

.dark-mode .source-level-card.assist .level-band,
.dark-mode .source-level-card.assist .level-tag {
  background: rgba(126, 184, 209, 0.14);
  color: #9DC9D9;
}

.dark-mode .level-tag {
  background: #20384A;
  color: #7EB8D1;
}

.dark-mode .level-item {
  border-top-color: #273847;
}
</style>
