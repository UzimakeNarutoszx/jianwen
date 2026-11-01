const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function toDate(value) {
  return value ? new Date(value) : new Date()
}

function pad(value) {
  return String(value).padStart(2, '0')
}

export function formatToday(value) {
  const date = toDate(value)
  return `${date.getMonth() + 1}月${date.getDate()}日 ${weekdays[date.getDay()]}`
}

export function formatDate(value) {
  const date = toDate(value)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function formatShortDate(value) {
  const date = toDate(value)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

export function formatDateTime(value) {
  const date = toDate(value)
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
