<template>
  <view :class="['page auth-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="auth-nav">
      <button class="back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view class="auth-head">
      <view class="brand-card">
        <image class="brand-logo" src="/static/brand-icon.png" mode="aspectFit" />
      </view>
      <view class="head-copy">
        <text class="trust-badge">安全同步</text>
        <text class="page-title">{{ pageTitle }}</text>
        <text class="subtle">{{ pageSubtitle }}</text>
      </view>
    </view>

    <view class="mode-switch">
      <button :class="['mode-button', mode === 'login' ? 'active' : '']" @click="switchMode('login')">登录</button>
      <button :class="['mode-button', mode === 'register' ? 'active' : '']" @click="switchMode('register')">注册</button>
      <button :class="['mode-button', mode === 'forgot' ? 'active' : '']" @click="switchMode('forgot')">重置密码</button>
    </view>

    <view class="auth-panel card">
      <view v-if="isRegister" class="field-group">
        <text class="field-label">昵称</text>
        <view class="field-shell">
          <view class="field-icon user-icon"></view>
          <input v-model.trim="form.nickname" class="field-input" maxlength="16" placeholder="用于展示的名字" placeholder-class="input-placeholder" />
        </view>
      </view>

      <view class="field-group">
        <text class="field-label">手机号</text>
        <view class="field-shell">
          <view class="field-icon phone-icon"></view>
          <input v-model.trim="form.phone" class="field-input" type="number" maxlength="11" placeholder="请输入手机号" placeholder-class="input-placeholder" />
        </view>
      </view>

      <view class="field-group">
        <text class="field-label">{{ isForgot ? '新密码' : '密码' }}</text>
        <view class="field-shell password-shell">
          <view class="field-icon lock-icon"></view>
          <input v-model="form.password" class="field-input password-input" password maxlength="32" placeholder="请输入密码" placeholder-class="input-placeholder" />
        </view>
      </view>

      <view v-if="isRegister || isForgot" class="field-group">
        <text class="field-label">确认密码</text>
        <view class="field-shell">
          <view class="field-icon lock-icon"></view>
          <input v-model="form.confirmPassword" class="field-input" password maxlength="32" placeholder="请再次输入密码" placeholder-class="input-placeholder" />
        </view>
      </view>

      <view v-if="isRegister || isForgot" class="field-group">
        <text class="field-label">验证码</text>
        <view class="field-shell sms-shell">
          <view class="field-icon sms-icon"></view>
          <input v-model.trim="form.smsCode" class="field-input sms-input" type="number" maxlength="6" placeholder="请输入 6 位验证码" placeholder-class="input-placeholder" />
          <button class="sms-button" :disabled="smsSending || smsCountdown > 0" @click="handleSendSms">{{ smsButtonText }}</button>
        </view>
      </view>

      <view v-if="isRegister" class="helper-row">
        <checkbox-group class="agree-row" @change="changeAgreement">
          <label class="agree-label">
            <checkbox class="agree-check" value="agreed" :checked="agreed" color="#1F5F7A" />
            <text class="agree-text">已阅读并同意</text>
            <text class="agree-link" @click.stop="openLegal">用户协议</text>
            <text class="agree-text">和</text>
            <text class="agree-link" @click.stop="openLegal">隐私政策</text>
          </label>
        </checkbox-group>
      </view>

      <button class="primary-button submit-button" :disabled="submitting" @click="submit">
        {{ submitting ? '提交中...' : submitText }}
      </button>
    </view>

    <view class="secondary-actions">
      <text class="security-line">手机号仅用于登录验证与账号同步</text>
      <button class="link-button" @click="switchMode(isRegister || isForgot ? 'login' : 'register')">
        {{ isRegister || isForgot ? '返回登录' : '没有账号，去注册' }}
      </button>
    </view>
  </view>
</template>

<script>
import { loginWithPassword, registerWithSms, resetPasswordBySms, sendSms } from '@/utils/api.js'

const AUTH_TOKEN_KEY = 'jianwen_auth_token'
const AUTH_USER_KEY = 'jianwen_auth_user'
const SAVED_LOGIN_KEY = 'jianwen_saved_login_credentials'
const LOGIN_EXPIRES_AT_KEY = 'jianwen_login_expires_at'
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
// Pages registered in pages.json tabBar must be reopened with switchTab.
const TAB_BAR_ROUTES = [
  '/pages/today/today',
  '/pages/discover/discover',
  '/pages/weekly/weekly',
  '/pages/ask/ask',
  '/pages/profile/profile'
]

function sanitizeRedirect(value) {
  let target = ''
  try { target = decodeURIComponent(String(value || '')) } catch (error) { target = '' }
  if (!target || target.charAt(0) !== '/') return ''
  if (target.indexOf('/pages/auth/login') === 0) return ''
  return target
}

export default {
  data() {
    return {
      mode: 'login',
      redirect: '',
      darkMode: false,
      fontSize: 'standard',
      submitting: false,
      smsSending: false,
      smsCountdown: 0,
      smsTimer: null,
      agreed: false,
      form: {
        nickname: '',
        phone: '',
        password: '',
        confirmPassword: '',
        smsCode: ''
      }
    }
  },
  computed: {
    isRegister() { return this.mode === 'register' },
    isForgot() { return this.mode === 'forgot' },
    pageTitle() {
      if (this.isRegister) return '创建见闻账号'
      if (this.isForgot) return '重置密码'
      return '登录见闻'
    },
    pageSubtitle() {
      if (this.isRegister) return '注册后可同步收藏、阅读历史和问问记录。'
      if (this.isForgot) return '输入手机号、验证码，并设置新密码。'
      return '继续同步你的收藏、阅读历史和问问记录。'
    },
    submitText() {
      if (this.isRegister) return '注册并登录'
      if (this.isForgot) return '重置密码'
      return '登录'
    },
    smsButtonText() {
      if (this.smsCountdown > 0) return `${this.smsCountdown}秒`
      return this.smsSending ? '发送中...' : '获取验证码'
    }
  },
  onLoad(options) {
    if (options && options.mode === 'register') this.mode = 'register'
    this.redirect = sanitizeRedirect(options && options.redirect)
    this.loadSavedLogin()
    if (this.mode === 'login') this.skipIfSessionValid()
  },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    if (this.mode === 'login') this.skipIfSessionValid()
  },
  beforeDestroy() {
    this.clearSmsTimer()
  },
  onUnload() {
    this.clearSmsTimer()
  },
  methods: {
    switchMode(mode) {
      this.mode = mode
      this.form.password = ''
      this.form.confirmPassword = ''
      this.form.smsCode = ''
      this.clearSmsTimer()
    },
    async handleSendSms() {
      const message = this.validatePhone()
      if (message) {
        uni.showToast({ title: message, icon: 'none' })
        return
      }
      if (this.smsSending || this.smsCountdown > 0) return

      this.smsSending = true
      try {
        const result = await sendSms(this.form.phone, this.isForgot ? 'reset_password' : 'register')
        uni.showToast({ title: result.message || '验证码已发送', icon: 'none' })
        this.startSmsCountdown()
      } catch (error) {
        uni.showToast({ title: error.message || '验证码发送失败', icon: 'none' })
      } finally {
        this.smsSending = false
      }
    },
    startSmsCountdown() {
      this.clearSmsTimer()
      this.smsCountdown = 60
      this.smsTimer = setInterval(() => {
        if (this.smsCountdown <= 1) {
          this.clearSmsTimer()
          return
        }
        this.smsCountdown -= 1
      }, 1000)
    },
    clearSmsTimer() {
      if (this.smsTimer) {
        clearInterval(this.smsTimer)
        this.smsTimer = null
      }
      this.smsCountdown = 0
    },
    changeAgreement(event) {
      this.agreed = event.detail.value.includes('agreed')
    },
    openLegal() {
      uni.navigateTo({ url: '/pages/settings/legal' })
    },
    async submit() {
      const message = this.validate()
      if (message) {
        uni.showToast({ title: message, icon: 'none' })
        return
      }

      this.submitting = true
      try {
        if (this.isForgot) {
          await resetPasswordBySms(this.form.phone, this.form.smsCode, this.form.password)
          uni.showToast({ title: '密码已重置', icon: 'success' })
          this.switchMode('login')
          return
        }

        const result = this.isRegister
          ? await registerWithSms({
              phone: this.form.phone,
              nickname: this.form.nickname,
              password: this.form.password,
              sms_code: this.form.smsCode
          })
          : await loginWithPassword(this.form.phone, this.form.password)

        uni.setStorageSync(AUTH_TOKEN_KEY, result.access_token)
        uni.setStorageSync(AUTH_USER_KEY, result.user)
        this.saveLoginSession()
        if (!this.isRegister) this.saveLoginCredentials()
        uni.showToast({ title: this.isRegister ? '注册成功' : '登录成功', icon: 'success' })
        setTimeout(() => this.goBack(), 650)
      } catch (error) {
        uni.showToast({ title: error.message || '请求失败', icon: 'none' })
      } finally {
        this.submitting = false
      }
    },
    validatePhone() {
      if (!this.form.phone) return '请填写手机号'
      if (!/^1\d{10}$/.test(this.form.phone)) return '手机号格式不正确'
      return ''
    },
    validate() {
      if (this.isRegister && !this.form.nickname) return '请填写昵称'
      const phoneMessage = this.validatePhone()
      if (phoneMessage) return phoneMessage
      if (!this.form.password || this.form.password.length < 6) return '密码至少 6 位'
      if ((this.isRegister || this.isForgot) && this.form.password !== this.form.confirmPassword) return '两次密码不一致'
      if ((this.isRegister || this.isForgot) && !/^\d{6}$/.test(this.form.smsCode)) return '请输入 6 位验证码'
      if (this.isRegister && !this.agreed) return '请先同意协议'
      return ''
    },
    loadSavedLogin() {
      const saved = uni.getStorageSync(SAVED_LOGIN_KEY)
      if (!saved || typeof saved !== 'object') return
      if (!this.form.phone && saved.phone) this.form.phone = saved.phone
      if (!this.form.password && saved.password) this.form.password = saved.password
    },
    saveLoginCredentials() {
      uni.setStorageSync(SAVED_LOGIN_KEY, {
        phone: this.form.phone,
        password: this.form.password,
        savedAt: Date.now()
      })
    },
    saveLoginSession() {
      uni.setStorageSync(LOGIN_EXPIRES_AT_KEY, Date.now() + SEVEN_DAYS_MS)
    },
    skipIfSessionValid() {
      const token = uni.getStorageSync(AUTH_TOKEN_KEY)
      const expiresAt = Number(uni.getStorageSync(LOGIN_EXPIRES_AT_KEY) || 0)
      if (!token || !expiresAt || expiresAt <= Date.now()) return

      uni.showToast({ title: '已登录', icon: 'success' })
      setTimeout(() => this.goBack(), 350)
    },
    goBack() {
      // Reached from an expired session: return the user to where they were.
      if (this.redirect) {
        const target = this.redirect
        this.redirect = ''
        const isTab = TAB_BAR_ROUTES.some(route => target === route || target.indexOf(`${route}?`) === 0)
        if (isTab) {
          uni.switchTab({ url: target, fail: () => uni.reLaunch({ url: target }) })
          return
        }
        const pages = getCurrentPages()
        const previous = pages.length > 1 ? pages[pages.length - 2] : null
        const previousUrl = previous ? `/${previous.route || previous.__route__ || ''}` : ''
        if (previousUrl && target.indexOf(previousUrl) === 0) {
          uni.navigateBack()
          return
        }
        uni.redirectTo({ url: target, fail: () => uni.reLaunch({ url: target }) })
        return
      }
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
.auth-page {
  position: relative;
  overflow: hidden;
}

.auth-nav {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 64rpx;
  margin-bottom: 26rpx;
}

.auth-head {
  display: flex;
  align-items: center;
  gap: 28rpx;
  margin-bottom: 42rpx;
}

.brand-card {
  position: relative;
  flex: 0 0 152rpx;
  width: 152rpx;
  height: 152rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255,255,255,0.92);
  border-radius: 36rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(255,255,255,0.58)),
    linear-gradient(135deg, rgba(212,170,78,0.22), rgba(31,95,122,0.1));
  box-shadow: 0 26rpx 70rpx rgba(31, 47, 58, 0.13);
}

.brand-card::after {
  content: '';
  position: absolute;
  right: 18rpx;
  bottom: 18rpx;
  width: 18rpx;
  height: 18rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
  box-shadow: 0 0 0 8rpx rgba(212,170,78,0.18);
}

.brand-logo {
  width: 106rpx;
  height: 106rpx;
  border-radius: 26rpx;
}

.head-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.trust-badge {
  align-self: flex-start;
  min-height: 40rpx;
  padding: 0 18rpx;
  border: 1rpx solid rgba(212,170,78,0.34);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.52);
  color: #8A651F;
  font-size: 22rpx;
  line-height: 40rpx;
  font-weight: 900;
}

.mode-switch {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10rpx;
  width: 100%;
  margin-bottom: 26rpx;
  padding: 10rpx;
  border: 1rpx solid rgba(255,255,255,0.82);
  border-radius: 24rpx;
  background: rgba(255,255,255,0.68);
  box-shadow: 0 20rpx 48rpx rgba(31, 47, 58, 0.08);
}

.mode-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 72rpx;
  border-radius: 18rpx;
  color: #5C6873;
  font-size: 25rpx;
  font-weight: 800;
}

.mode-button.active {
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
  box-shadow: 0 14rpx 32rpx rgba(31, 95, 122, 0.2);
}

.auth-panel {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
  width: 100%;
  padding: 38rpx 34rpx 36rpx;
  border-color: rgba(255,255,255,0.9);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.86), rgba(255,255,255,0.68)),
    rgba(255,255,255,0.72);
  box-shadow: 0 28rpx 76rpx rgba(31, 47, 58, 0.12);
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.field-label {
  color: #14212B;
  font-size: 25rpx;
  font-weight: 800;
}

.field-shell {
  display: flex;
  align-items: center;
  gap: 18rpx;
  width: 100%;
  height: 84rpx;
  padding: 0 18rpx 0 20rpx;
  border: 1rpx solid rgba(220,229,234,0.96);
  border-radius: 18rpx;
  background: rgba(247,250,252,0.82);
}

.field-icon {
  position: relative;
  flex: 0 0 34rpx;
  width: 34rpx;
  height: 34rpx;
  color: #1F5F7A;
}

.user-icon::before {
  content: '';
  position: absolute;
  top: 2rpx;
  left: 10rpx;
  width: 14rpx;
  height: 14rpx;
  border: 3rpx solid currentColor;
  border-radius: 999rpx;
}

.user-icon::after {
  content: '';
  position: absolute;
  left: 5rpx;
  bottom: 2rpx;
  width: 24rpx;
  height: 14rpx;
  border: 3rpx solid currentColor;
  border-top-left-radius: 18rpx;
  border-top-right-radius: 18rpx;
  border-bottom: 0;
}

.phone-icon {
  border: 3rpx solid currentColor;
  border-radius: 9rpx;
}

.phone-icon::after {
  content: '';
  position: absolute;
  left: 12rpx;
  bottom: 4rpx;
  width: 8rpx;
  height: 3rpx;
  border-radius: 999rpx;
  background: currentColor;
}

.lock-icon::before {
  content: '';
  position: absolute;
  left: 7rpx;
  top: 1rpx;
  width: 20rpx;
  height: 18rpx;
  border: 3rpx solid currentColor;
  border-bottom: 0;
  border-radius: 18rpx 18rpx 0 0;
}

.lock-icon::after {
  content: '';
  position: absolute;
  left: 4rpx;
  bottom: 2rpx;
  width: 26rpx;
  height: 20rpx;
  border-radius: 7rpx;
  background: currentColor;
}

.sms-icon {
  border: 3rpx solid currentColor;
  border-radius: 8rpx;
}

.sms-icon::after {
  content: '';
  position: absolute;
  right: 4rpx;
  bottom: -8rpx;
  width: 12rpx;
  height: 12rpx;
  border-left: 3rpx solid currentColor;
  border-bottom: 3rpx solid currentColor;
  transform: rotate(-18deg);
}

.field-input {
  flex: 1;
  min-width: 0;
  height: 82rpx;
  padding: 0;
  color: #14212B;
  font-size: 28rpx;
}

.input-placeholder {
  color: #95A1AA;
}

.password-shell,
.sms-shell {
  display: flex;
  align-items: center;
}

.password-input,
.sms-input {
  flex: 1;
  min-width: 0;
}

.sms-button {
  flex: 0 0 176rpx;
  height: 62rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
  font-size: 24rpx;
  font-weight: 900;
}

.sms-button[disabled] {
  opacity: 0.62;
}

.helper-row {
  min-height: 44rpx;
}

.agree-row,
.agree-label {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.agree-check {
  transform: scale(0.74);
  transform-origin: left center;
}

.agree-text {
  color: #5C6873;
  font-size: 23rpx;
  line-height: 1.4;
}

.agree-link {
  color: #1F5F7A;
  font-size: 23rpx;
  line-height: 1.4;
  font-weight: 900;
}

.submit-button {
  width: 100%;
  margin-top: 4rpx;
}

.submit-button[disabled] {
  opacity: 0.68;
}

.secondary-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  margin-top: 30rpx;
}

.security-line {
  flex: 1;
  min-width: 0;
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.45;
}

.link-button {
  flex: 0 0 auto;
  color: #1F5F7A;
  font-size: 26rpx;
  font-weight: 800;
}

.font-large .mode-button,
.font-large .field-label,
.font-large .link-button {
  font-size: 29rpx;
}

.font-large .field-input {
  font-size: 31rpx;
}

.font-small .mode-button,
.font-small .field-label,
.font-small .link-button {
  font-size: 23rpx;
}

.font-small .field-input {
  font-size: 26rpx;
}

.dark-mode .brand-card,
.dark-mode .mode-switch {
  border-color: rgba(126,184,209,0.14);
  background: rgba(23,35,49,0.72);
  box-shadow: 0 24rpx 64rpx rgba(0, 0, 0, 0.24);
}

.dark-mode .auth-panel {
  border-color: #273847;
  background:
    linear-gradient(180deg, rgba(23,35,49,0.92), rgba(17,27,39,0.84)),
    #172331;
}

.dark-mode .trust-badge {
  border-color: rgba(187,141,45,0.28);
  background: rgba(187,141,45,0.12);
  color: #D8B96D;
}

.dark-mode .field-label {
  color: #F4F7FA;
}

.dark-mode .field-shell {
  border-color: #314455;
  background: rgba(14,23,32,0.62);
}

.dark-mode .field-input {
  color: #F4F7FA;
}

.dark-mode .field-icon {
  color: #7EB8D1;
}

.dark-mode .sms-button {
  background: #20384A;
  color: #7EB8D1;
}

.dark-mode .agree-text,
.dark-mode .security-line {
  color: #B6C2CC;
}

.dark-mode .agree-link {
  color: #7EB8D1;
}

@media screen and (max-width: 360px) {
  .auth-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .mode-button {
    font-size: 23rpx;
  }

  .auth-panel {
    padding-left: 28rpx;
    padding-right: 28rpx;
  }

  .sms-button {
    flex-basis: 154rpx;
    font-size: 22rpx;
  }
}
</style>
