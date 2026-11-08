<script>
import { installReadingActivity, readingActivity, resumeReadingActivity } from '@/utils/reading-activity.js'
import { checkForAppUpdate } from '@/utils/app-updater.js'
export default {
  onLaunch() {
    installReadingActivity()
    checkForAppUpdate()
    console.log('Jianwen launched')
  },
  onShow() { resumeReadingActivity(); checkForAppUpdate() },
  onHide() { readingActivity.pause() }
}
</script>

<style>
page {
  min-height: 100%;
  background: #F5F7F4;
  color: #14212B;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif;
}

view,
text,
button,
input,
textarea {
  box-sizing: border-box;
}

button {
  margin: 0;
  padding: 0;
  background: transparent;
  line-height: 1.4;
}

button::after {
  border: none;
}

.page {
  min-height: 100vh;
  padding: calc(96rpx + constant(safe-area-inset-top)) 48rpx calc(92rpx + constant(safe-area-inset-bottom));
  padding: calc(96rpx + env(safe-area-inset-top)) 48rpx calc(92rpx + env(safe-area-inset-bottom));
  background:
    radial-gradient(circle at 16% 0%, rgba(214, 184, 112, 0.28) 0, rgba(214, 184, 112, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(31, 95, 122, 0.18) 0, rgba(31, 95, 122, 0) 330rpx),
    linear-gradient(180deg, #F8F5EC 0%, #EDF5F7 460rpx, #F5F7F4 100%);
}

/* #ifdef APP-PLUS */
.page {
  padding-top: calc(96rpx + var(--status-bar-height));
}
/* #endif */

.index-page,
.redirect-page,
.discover-page,
.profile-page,
.category-page,
.search-page,
.auth-page,
.article-page,
.classics-detail-page,
.settings-page,
.list-page,
.record-page {
  background:
    radial-gradient(circle at 16% 0%, rgba(214, 184, 112, 0.28) 0, rgba(214, 184, 112, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(31, 95, 122, 0.18) 0, rgba(31, 95, 122, 0) 330rpx),
    linear-gradient(180deg, #F8F5EC 0%, #EDF5F7 460rpx, #F5F7F4 100%) !important;
}

.page.with-tabbar {
  padding-bottom: calc(220rpx + constant(safe-area-inset-bottom));
  padding-bottom: calc(220rpx + env(safe-area-inset-bottom));
}

.topbar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 156rpx;
  padding: 30rpx 30rpx;
  margin: -18rpx -14rpx 54rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.82);
  border-radius: 32rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.86), rgba(255,255,255,0.5)),
    linear-gradient(135deg, rgba(245,235,207,0.84), rgba(226,240,244,0.72));
  box-shadow: 0 24rpx 64rpx rgba(48, 65, 72, 0.11);
}

.topbar::after {
  content: '';
  position: absolute;
  top: -90rpx;
  right: -70rpx;
  width: 220rpx;
  height: 220rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.2);
  pointer-events: none;
}

.brand-title {
  position: relative;
  z-index: 1;
  font-size: 48rpx;
  line-height: 1.18;
  font-weight: 900;
  color: #101D28;
}

.page-title {
  position: relative;
  z-index: 1;
  font-size: 46rpx;
  line-height: 1.2;
  font-weight: 900;
  color: #101D28;
}

.subtle {
  position: relative;
  z-index: 1;
  color: #66737B;
  font-size: 26rpx;
  line-height: 1.6;
}

.card {
  border: 1rpx solid rgba(255,255,255,0.88);
  border-radius: 28rpx;
  background: rgba(255,255,255,0.82);
  box-shadow: 0 24rpx 60rpx rgba(31, 47, 58, 0.1);
}

.section-title {
  display: block;
  margin: 70rpx 0 34rpx;
  color: #14212B;
  font-size: 34rpx;
  line-height: 1.35;
  font-weight: 900;
}

.tag {
  display: inline-flex;
  align-items: center;
  min-height: 40rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
  font-size: 22rpx;
  font-weight: 900;
}

.source-line {
  color: #7C8790;
  font-size: 24rpx;
  line-height: 1.5;
}

.article-update-date {
  display: block;
  margin-top: 12rpx;
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}

.dark-mode .article-update-date {
  color: #B6C2CC;
}

.primary-button {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 90rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #fff;
  font-size: 28rpx;
  font-weight: 900;
  box-shadow: 0 18rpx 42rpx rgba(31, 95, 122, 0.2);
}

.ghost-button {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 82rpx;
  padding: 0 34rpx;
  border: 1rpx solid rgba(31,95,122,0.2);
  border-radius: 999rpx;
  color: #143E52;
  font-size: 26rpx;
  background: rgba(255,255,255,0.72);
  box-shadow: 0 16rpx 36rpx rgba(20, 33, 43, 0.08);
}

.detail-nav,
.settings-nav,
.search-nav,
.auth-nav,
.classics-nav {
  position: relative;
  min-height: 56rpx;
}

.back-button {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  position: relative !important;
  flex: 0 0 56rpx !important;
  width: 56rpx !important;
  height: 56rpx !important;
  min-width: 56rpx !important;
  max-width: 56rpx !important;
  min-height: 56rpx !important;
  max-height: 56rpx !important;
  box-sizing: border-box !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 1rpx solid rgba(31,95,122,0.14) !important;
  border-radius: 999rpx !important;
  background: rgba(255,255,255,0.72) !important;
  color: #1F5F7A !important;
  box-shadow: 0 12rpx 32rpx rgba(20, 33, 43, 0.08) !important;
  line-height: 1 !important;
  text-align: center !important;
  overflow: visible !important;
}

button.back-button::after {
  border: 0 !important;
}

/* 56rpx visual size kept; a transparent pad lifts the tap target to 88rpx. */
.back-button::before {
  content: '';
  position: absolute;
  top: -16rpx;
  right: -16rpx;
  bottom: -16rpx;
  left: -16rpx;
}

.back-symbol {
  display: inline-block !important;
  flex: 0 0 14rpx !important;
  width: 14rpx !important;
  height: 14rpx !important;
  box-sizing: border-box !important;
  border-left: 4rpx solid currentColor !important;
  border-bottom: 4rpx solid currentColor !important;
  border-radius: 2rpx !important;
  transform: rotate(45deg) translate(2rpx, -2rpx) !important;
}

.detail-nav .back-button,
.settings-nav .back-button,
.auth-nav .back-button,
.classics-nav .back-button {
  position: absolute !important;
  left: 0 !important;
  top: 0 !important;
  right: auto !important;
  bottom: auto !important;
}

.detail-nav .article-back-button {
  position: relative !important;
  left: auto !important;
  top: auto !important;
  right: auto !important;
  bottom: auto !important;
}

.channel-topbar .back-button,
.search-toolbar .back-button {
  position: relative !important;
  left: auto !important;
  top: auto !important;
  right: auto !important;
  bottom: auto !important;
}

.channel-topbar .back-button {
  align-self: flex-start !important;
  margin-right: auto !important;
}

.reader-topbar .reader-back-button {
  position: absolute !important;
  left: 28rpx !important;
  bottom: 16rpx !important;
}

.dark-mode .back-button {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.82) !important;
  color: #7EB8D1 !important;
}

.page-head,
.settings-head,
.category-head,
.auth-head {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  padding: 34rpx;
  margin: 0 0 48rpx;
  border: 1rpx solid rgba(255,255,255,0.82);
  border-radius: 30rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.86), rgba(255,255,255,0.5)),
    linear-gradient(135deg, rgba(245,235,207,0.84), rgba(226,240,244,0.72));
  box-shadow: 0 24rpx 64rpx rgba(48, 65, 72, 0.1);
}

.page-head::after,
.settings-head::after,
.category-head::after,
.auth-head::after {
  content: '';
  position: absolute;
  top: -76rpx;
  right: -58rpx;
  width: 210rpx;
  height: 210rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.18);
  pointer-events: none;
}

.article-card,
.record-card,
.content-card,
.option-card,
.preview-card,
.auth-panel,
.mode-switch,
.search-box,
.source-card,
.impact-card,
.timeline-card,
.ask-card,
.body-card,
.empty-card,
.hero-card,
.edit-card,
.account-card,
.function-row,
.follow-card,
.menu-card {
  border-color: rgba(255,255,255,0.88) !important;
  border-radius: 28rpx !important;
  background: rgba(255,255,255,0.82) !important;
  box-shadow: 0 24rpx 60rpx rgba(31, 47, 58, 0.1) !important;
}

.field-input,
.field-textarea,
.composer-input,
.ask-input,
.search-input {
  color: #14212B;
}

.article-card:active,
.record-card:active,
.topic-card:active,
.classic-card:active,
.feature-card:active,
.update-item:active,
.menu-item:active,
.function-item:active,
.font-option:active,
.primary-button:active,
.ghost-button:active,
.login-button:active,
.send-button:active {
  transform: scale(0.985);
  opacity: 0.92;
}

.dark-mode .ghost-button {
  border-color: #273847;
  background: #172331;
  color: #D7E2EA;
}

.dark-mode .page-head,
.dark-mode .settings-head,
.dark-mode .category-head,
.dark-mode .auth-head,
.dark-mode .article-card,
.dark-mode .record-card,
.dark-mode .content-card,
.dark-mode .option-card,
.dark-mode .preview-card,
.dark-mode .auth-panel,
.dark-mode .mode-switch,
.dark-mode .search-box,
.dark-mode .source-card,
.dark-mode .impact-card,
.dark-mode .timeline-card,
.dark-mode .ask-card,
.dark-mode .body-card,
.dark-mode .empty-card,
.dark-mode .hero-card,
.dark-mode .edit-card,
.dark-mode .account-card,
.dark-mode .function-row,
.dark-mode .follow-card,
.dark-mode .menu-card {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.86) !important;
  box-shadow: 0 24rpx 60rpx rgba(0, 0, 0, 0.22) !important;
}

.dark-mode .tag {
  background: #20384A;
  color: #7EB8D1;
}

.dark-mode,
.dark-mode.page,
.dark-mode.ask-page,
.dark-mode.settings-page {
  background:
    radial-gradient(circle at 16% 0%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(75, 154, 187, 0.16) 0, rgba(75, 154, 187, 0) 330rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
  color: #F4F7FA !important;
}

.dark-mode.index-page,
.dark-mode.redirect-page,
.dark-mode.discover-page,
.dark-mode.profile-page,
.dark-mode.category-page,
.dark-mode.search-page,
.dark-mode.auth-page,
.dark-mode.article-page,
.dark-mode.classics-detail-page,
.dark-mode.settings-page,
.dark-mode.list-page,
.dark-mode.record-page {
  background:
    radial-gradient(circle at 16% 0%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(75, 154, 187, 0.16) 0, rgba(75, 154, 187, 0) 330rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
}

.dark-mode .topbar {
  border-color: rgba(126,184,209,0.14) !important;
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08)) !important;
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28) !important;
}

.dark-mode .brand-title,
.dark-mode .page-title,
.dark-mode .section-title,
.dark-mode .content-title,
.dark-mode .content-heading,
.dark-mode .option-title,
.dark-mode .preview-title,
.dark-mode .account-title,
.dark-mode .function-label,
.dark-mode .menu-label,
.dark-mode .feature-title,
.dark-mode .update-title,
.dark-mode .followup-title,
.dark-mode .block-title,
.dark-mode .mini-title,
.dark-mode .section-heading,
.dark-mode .answer-title {
  color: #F4F7FA !important;
}

.dark-mode .subtle,
.dark-mode .date-text,
.dark-mode .source-line,
.dark-mode .content-body,
.dark-mode .option-desc,
.dark-mode .preview-body,
.dark-mode .account-desc,
.dark-mode .menu-desc,
.dark-mode .setting-value,
.dark-mode .feature-desc,
.dark-mode .feature-tags,
.dark-mode .message-label,
.dark-mode .message-source,
.dark-mode .summary-text,
.dark-mode .section-body,
.dark-mode .answer-text {
  color: #B6C2CC !important;
}

.dark-mode .card,
.dark-mode .search-box,
.dark-mode .prompt-card,
.dark-mode .followup-card,
.dark-mode .composer,
.dark-mode .composer-input,
.dark-mode .summary-card,
.dark-mode .answer-box,
.dark-mode .ask-input-row {
  border-color: #273847 !important;
  background: #172331 !important;
}

.dark-mode .topic-pill,
.dark-mode .function-icon-wrap,
.dark-mode .followup-chip,
.dark-mode .tool-button,
.dark-mode .impact-tag,
.dark-mode .question-chip,
.dark-mode .source-level {
  background: #20384A !important;
  color: #7EB8D1 !important;
}

/* Font enlargement pass: auxiliary text only. Titles, pills, cards and buttons keep their UI sizing. */
.subtle,
.date-text,
.source-line,
.section-note,
.page-end,
.meta,
.read-time,
.hero-kicker,
.hero-copy,
.hero-desc,
.hero-foot-item,
.section-eyebrow,
.chat-eyebrow,
.feature-kicker,
.console-kicker,
.console-desc,
.head-kicker,
.block-kicker,
.section-kicker,
.search-hint,
.banner-desc,
.topic-desc,
.quote-label,
.quote-source,
.quote-subtitle,
.quote-body,
.progress-desc,
.relation-label,
.relation-text,
.summary-note,
.summary-text,
.ask-desc,
.timeline-step,
.classic-desc,
.classic-meta,
.classic-source,
.feature-desc,
.feature-tags,
.article-desc,
.book-desc,
.block-body,
.block-label,
.chapter-summary,
.paragraph,
.content-body,
.option-desc,
.option-meta,
.preview-body,
.preview-kicker,
.preview-status,
.sample-small,
.account-desc,
.ask-input,
.sync-row,
.field-label,
.metric-label,
.chat-state,
.group-desc,
.group-count,
.menu-desc,
.setting-value,
.agree-text,
.security-line,
.channel-label,
.catalog-count,
.cover-kicker,
.cover-imprint,
.page-label,
.count-label,
.read-meta,
.source-label,
.source-link,
.read-date,
.result-note,
.meta-label,
.meta-value,
.message-label,
.message-source,
.message-thinking,
.message.context .message-text,
.prompt-text,
.source-head,
.source-text,
.answer-text,
.eyebrow,
.empty-desc,
.step-desc,
.level-desc,
.record-time,
.stat-label,
.top-state,
.paper-header,
.paper-footer,
.progress-chapter,
.progress-text {
  font-size: 28rpx !important;
}

.source-line,
.date-text,
.section-note,
.read-time,
.meta,
.hero-kicker,
.section-eyebrow,
.chat-eyebrow,
.feature-kicker,
.console-kicker,
.head-kicker,
.block-kicker,
.section-kicker,
.search-hint,
.topic-desc,
.quote-label,
.quote-source,
.quote-subtitle,
.relation-label,
.summary-note,
.ask-desc,
.classic-meta,
.classic-source,
.option-meta,
.preview-kicker,
.preview-status,
.ask-input,
.field-label,
.metric-label,
.chat-state,
.group-count,
.agree-text,
.security-line,
.channel-label,
.catalog-count,
.cover-kicker,
.cover-imprint,
.page-label,
.count-label,
.read-meta,
.source-label,
.source-link,
.read-date,
.result-note,
.meta-label,
.meta-value,
.message-label,
.message-source,
.message-thinking,
.source-head,
.source-text,
.eyebrow,
.record-time,
.stat-label,
.top-state,
.paper-header,
.paper-footer,
.progress-chapter,
.progress-text {
  font-size: 26rpx !important;
}

.content-body,
.section-body,
.summary-text,
.timeline-step,
.message.context .message-text,
.prompt-text,
.paragraph,
.preview-body,
.quote-body,
.block-body {
  font-size: 32rpx !important;
}

.font-small .subtle,
.font-small .date-text,
.font-small .source-line,
.font-small .section-note,
.font-small .page-end,
.font-small .meta,
.font-small .read-time,
.font-small .hero-kicker,
.font-small .hero-copy,
.font-small .hero-desc,
.font-small .hero-foot-item,
.font-small .section-eyebrow,
.font-small .chat-eyebrow,
.font-small .feature-kicker,
.font-small .console-kicker,
.font-small .console-desc,
.font-small .head-kicker,
.font-small .block-kicker,
.font-small .section-kicker,
.font-small .search-hint,
.font-small .banner-desc,
.font-small .topic-desc,
.font-small .quote-label,
.font-small .quote-source,
.font-small .quote-subtitle,
.font-small .quote-body,
.font-small .progress-desc,
.font-small .relation-label,
.font-small .relation-text,
.font-small .summary-note,
.font-small .summary-text,
.font-small .ask-desc,
.font-small .timeline-step,
.font-small .classic-desc,
.font-small .classic-meta,
.font-small .classic-source,
.font-small .feature-desc,
.font-small .feature-tags,
.font-small .article-desc,
.font-small .book-desc,
.font-small .block-body,
.font-small .block-label,
.font-small .chapter-summary,
.font-small .paragraph,
.font-small .content-body,
.font-small .option-desc,
.font-small .option-meta,
.font-small .preview-body,
.font-small .preview-kicker,
.font-small .preview-status,
.font-small .sample-small,
.font-small .account-desc,
.font-small .ask-input,
.font-small .sync-row,
.font-small .field-label,
.font-small .metric-label,
.font-small .chat-state,
.font-small .group-desc,
.font-small .group-count,
.font-small .menu-desc,
.font-small .setting-value,
.font-small .agree-text,
.font-small .security-line,
.font-small .channel-label,
.font-small .catalog-count,
.font-small .cover-kicker,
.font-small .cover-imprint,
.font-small .page-label,
.font-small .count-label,
.font-small .read-meta,
.font-small .source-label,
.font-small .source-link,
.font-small .read-date,
.font-small .result-note,
.font-small .meta-label,
.font-small .meta-value,
.font-small .message-label,
.font-small .message-source,
.font-small .message-thinking,
.font-small .message.context .message-text,
.font-small .prompt-text,
.font-small .source-head,
.font-small .source-text,
.font-small .answer-text,
.font-small .eyebrow,
.font-small .empty-desc,
.font-small .step-desc,
.font-small .level-desc,
.font-small .record-time,
.font-small .stat-label,
.font-small .top-state,
.font-small .paper-header,
.font-small .paper-footer,
.font-small .progress-chapter,
.font-small .progress-text {
  font-size: 26rpx !important;
}

.font-large .subtle,
.font-large .date-text,
.font-large .source-line,
.font-large .section-note,
.font-large .page-end,
.font-large .meta,
.font-large .read-time,
.font-large .hero-kicker,
.font-large .hero-copy,
.font-large .hero-desc,
.font-large .hero-foot-item,
.font-large .section-eyebrow,
.font-large .chat-eyebrow,
.font-large .feature-kicker,
.font-large .console-kicker,
.font-large .console-desc,
.font-large .head-kicker,
.font-large .block-kicker,
.font-large .section-kicker,
.font-large .search-hint,
.font-large .banner-desc,
.font-large .topic-desc,
.font-large .quote-label,
.font-large .quote-source,
.font-large .quote-subtitle,
.font-large .quote-body,
.font-large .progress-desc,
.font-large .relation-label,
.font-large .relation-text,
.font-large .summary-note,
.font-large .summary-text,
.font-large .ask-desc,
.font-large .timeline-step,
.font-large .classic-desc,
.font-large .classic-meta,
.font-large .classic-source,
.font-large .feature-desc,
.font-large .feature-tags,
.font-large .article-desc,
.font-large .book-desc,
.font-large .block-body,
.font-large .block-label,
.font-large .chapter-summary,
.font-large .paragraph,
.font-large .content-body,
.font-large .option-desc,
.font-large .option-meta,
.font-large .preview-body,
.font-large .preview-kicker,
.font-large .preview-status,
.font-large .sample-small,
.font-large .account-desc,
.font-large .ask-input,
.font-large .sync-row,
.font-large .field-label,
.font-large .metric-label,
.font-large .chat-state,
.font-large .group-desc,
.font-large .group-count,
.font-large .menu-desc,
.font-large .setting-value,
.font-large .agree-text,
.font-large .security-line,
.font-large .channel-label,
.font-large .catalog-count,
.font-large .cover-kicker,
.font-large .cover-imprint,
.font-large .page-label,
.font-large .count-label,
.font-large .read-meta,
.font-large .source-label,
.font-large .source-link,
.font-large .read-date,
.font-large .result-note,
.font-large .meta-label,
.font-large .meta-value,
.font-large .message-label,
.font-large .message-source,
.font-large .message-thinking,
.font-large .message.context .message-text,
.font-large .prompt-text,
.font-large .source-head,
.font-large .source-text,
.font-large .answer-text,
.font-large .eyebrow,
.font-large .empty-desc,
.font-large .step-desc,
.font-large .level-desc,
.font-large .record-time,
.font-large .stat-label,
.font-large .top-state,
.font-large .paper-header,
.font-large .paper-footer,
.font-large .progress-chapter,
.font-large .progress-text {
  font-size: 30rpx !important;
}

.font-large .content-body,
.font-large .section-body,
.font-large .summary-text,
.font-large .timeline-step,
.font-large .message.context .message-text,
.font-large .prompt-text,
.font-large .paragraph,
.font-large .preview-body,
.font-large .quote-body,
.font-large .block-body {
  font-size: 34rpx !important;
}

/* Shared mobile design tokens and cross-page interaction polish. */
:root {
  --jw-ink: #183238;
  --jw-muted: #637477;
  --jw-blue: #28645e;
  --jw-blue-dark: #193e3a;
  --jw-gold: #c8a86d;
  --jw-paper: #f4f5f1;
  --jw-mist: #e9efea;
  --jw-line: #dae1dc;
  --jw-focus: rgba(40, 100, 94, .18);
  --jw-focus-strong: rgba(40, 100, 94, .2);
  --jw-focus-halo: rgba(40, 100, 94, .08);
  --jw-surface-page: #f4f5f1;
  --jw-surface-card: #f7f8f4;
  --jw-surface-float: #fafbf8;
  --jw-surface-overlay: #fcfcfa;
}

page {
  text-wrap: pretty;
  font-variant-numeric: tabular-nums;
  overflow-x: clip;
}

.page,
.card,
.topbar,
.page-head,
.settings-head,
.category-head,
.auth-head {
  min-width: 0;
}

.page {
  overflow-wrap: anywhere;
}

:is(.page-title, .section-title, .content-title, .content-heading, .option-title, .preview-title, .account-title, .feature-title, .update-title, .block-title, .mini-title, .answer-title) {
  text-wrap: balance;
}

:is(input, textarea, .composer-input, .ask-input, .search-box):focus,
:is(input, textarea, .composer-input, .ask-input, .search-box):focus-visible {
  outline: 0;
  border-color: transparent;
  box-shadow: 0 0 0 2rpx var(--jw-focus), 0 0 0 8rpx var(--jw-focus-halo);
  transition: background-color .14s ease;
}

button:focus-visible,
[role="button"]:focus-visible,
[tabindex]:focus-visible {
  outline: 0;
  box-shadow: 0 0 0 2rpx var(--jw-focus-strong), 0 0 0 8rpx var(--jw-focus-halo);
}

:is(.icon, [class$="-icon"], [class*="-icon-"]) { vertical-align: -.125em; }

.dark-mode {
  --jw-surface-page: #182421;
  --jw-surface-card: #1b2824;
  --jw-surface-float: #1e2b26;
  --jw-surface-overlay: #202e29;
}

.dark-mode :is(.brand-title, .page-title, .section-title, .content-title, .content-heading, .option-title, .preview-title, .account-title, .function-label, .menu-label, .feature-title, .update-title, .followup-title, .block-title, .mini-title, .section-heading, .answer-title, .article-title, .archive-title) {
  font-weight: 360;
}

.dark-mode :is(strong, b, .metric-value, .read-state, .favorite-text, .message-label, .option-value) {
  font-weight: 360;
}

.dark-mode {
  font-weight: 240;
}

.dark-mode :is(.card, .search-box, .prompt-card, .followup-card, .composer, .composer-input, .summary-card, .answer-box, .ask-input-row) {
  border-color: rgba(219, 239, 241, .07);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: .01ms !important;
  }
}
</style>
