// Policy answers stay in each page instance; only public keys can be sent to 问问.
export function pendingQuestion(kind, key, title) {
  uni.setStorageSync('jianwen_pending_ask_context', { [kind === 'issue' ? 'issueKey' : 'policyKey']: key, title, from: kind })
  uni.switchTab({ url: '/pages/ask/ask' })
}

export function openOfficialUrl(value) {
  if (!/^https?:\/\//i.test(value || '')) return
  // #ifdef H5
  window.open(value, '_blank', 'noopener,noreferrer')
  return
  // #endif
  // #ifdef APP-PLUS
  plus.runtime.openURL(value)
  return
  // #endif
  uni.setClipboardData({ data: value })
}

export const resultLabels = { potentially_eligible: '可能符合条件', not_eligible: '暂不符合条件', insufficient_information: '信息不足，暂无法判断' }
export const checkLabels = { met: '已满足', not_met: '未满足', unknown: '待确认' }
export const stageLabel = value => ({ consulting: '征求意见', published: '已发布', implementing: '实施中', ended: '已结束', ongoing: '持续跟进' }[value] || value)
export const policyUnavailable = policy => !policy.available || (policy.review_expires_at && Date.parse(`${policy.review_expires_at}T23:59:59+08:00`) < Date.now())
