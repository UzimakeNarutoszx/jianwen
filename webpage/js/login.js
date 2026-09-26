(function () {
  const $ = selector => document.querySelector(selector)
  const form = $('#auth-form')
  const state = $('#auth-state')
  const submit = $('#submit-button')
  const smsButton = $('#sms-button')
  const switchButton = $('#switch-button')
  const params = new URLSearchParams(location.search)
  let mode = ['login', 'register', 'forgot'].includes(params.get('mode')) ? params.get('mode') : 'login'
  let countdownTimer = null

  function setState(message, isError) {
    state.textContent = message || '\u00a0'
    state.style.color = isError ? '#a94343' : ''
  }

  function stopCountdown() {
    if (countdownTimer) clearInterval(countdownTimer)
    countdownTimer = null
    smsButton.disabled = false
    smsButton.textContent = '获取验证码'
  }

  function startCountdown() {
    stopCountdown()
    let seconds = 60
    smsButton.disabled = true
    smsButton.textContent = `${seconds} 秒后重试`
    countdownTimer = setInterval(() => {
      seconds -= 1
      if (seconds <= 0) {
        stopCountdown()
        return
      }
      smsButton.textContent = `${seconds} 秒后重试`
    }, 1000)
  }

  function setMode(nextMode) {
    mode = ['login', 'register', 'forgot'].includes(nextMode) ? nextMode : 'login'
    const needsCode = mode !== 'login'
    document.querySelectorAll('.auth-tab').forEach(tab => {
      const active = tab.dataset.mode === mode
      tab.classList.toggle('active', active)
      tab.setAttribute('aria-selected', String(active))
    })
    document.querySelectorAll('.register-only').forEach(node => node.classList.toggle('visible', mode === 'register'))
    document.querySelectorAll('.confirm-only,.code-only').forEach(node => node.classList.toggle('visible', needsCode))
    $('#nickname').required = mode === 'register'
    $('#confirm-password').required = needsCode
    $('#sms-code').required = needsCode
    $('#agreement').required = mode === 'register'
    $('#password').autocomplete = mode === 'login' ? 'current-password' : 'new-password'
    $('#auth-title').textContent = mode === 'login' ? '登录见闻' : mode === 'register' ? '创建见闻账号' : '重置密码'
    $('#auth-subtitle').textContent = mode === 'login'
      ? '使用见闻软件中的手机号和密码登录。'
      : mode === 'register'
        ? '通过手机号验证码创建后端账号。'
        : '验证手机号后设置新的登录密码。'
    $('#password-label').textContent = mode === 'forgot' ? '新密码' : '密码'
    submit.textContent = mode === 'login' ? '登录' : mode === 'register' ? '注册并登录' : '重置密码'
    switchButton.textContent = mode === 'login' ? '没有账号，去注册' : '返回密码登录'
    stopCountdown()
    setState('')

    const url = new URL(location.href)
    if (mode === 'login') url.searchParams.delete('mode')
    else url.searchParams.set('mode', mode)
    history.replaceState(null, '', url)
  }

  function validatePhone() {
    const phone = $('#phone').value.trim()
    return /^1\d{10}$/.test(phone) ? '' : '手机号格式不正确'
  }

  function validateForm() {
    if (mode === 'register' && !$('#nickname').value.trim()) return '请填写昵称'
    const phoneError = validatePhone()
    if (phoneError) return phoneError
    if ($('#password').value.length < 6) return '密码至少 6 位'
    if (mode !== 'login' && $('#password').value !== $('#confirm-password').value) return '两次密码不一致'
    if (mode !== 'login' && !/^\d{6}$/.test($('#sms-code').value.trim())) return '请输入 6 位验证码'
    if (mode === 'register' && !$('#agreement').checked) return '请先同意用户协议和隐私政策'
    return ''
  }

  function returnTarget() {
    const value = params.get('return') || params.get('next')
    if (!value) return new URL('../index.html', location.href).href
    try {
      const target = new URL(value, location.href)
      return target.origin === location.origin ? target.href : new URL('../index.html', location.href).href
    } catch {
      return new URL('../index.html', location.href).href
    }
  }

  document.querySelectorAll('.auth-tab').forEach(tab => tab.addEventListener('click', () => setMode(tab.dataset.mode)))
  switchButton.addEventListener('click', () => setMode(mode === 'login' ? 'register' : 'login'))

  smsButton.addEventListener('click', async () => {
    const phoneError = validatePhone()
    if (phoneError) {
      setState(phoneError, true)
      return
    }
    smsButton.disabled = true
    setState('正在请求验证码…')
    try {
      const result = await window.jianwenApi.sendSms($('#phone').value.trim(), mode === 'forgot' ? 'reset_password' : 'register')
      setState(result.message || '验证码已发送')
      startCountdown()
    } catch (error) {
      smsButton.disabled = false
      setState(error.message, true)
    }
  })

  form.addEventListener('submit', async event => {
    event.preventDefault()
    const validationError = validateForm()
    if (validationError) {
      setState(validationError, true)
      return
    }

    const phone = $('#phone').value.trim()
    const password = $('#password').value
    const smsCode = $('#sms-code').value.trim()
    submit.disabled = true
    setState('正在连接见闻后端…')
    try {
      if (mode === 'register') {
        await window.jianwenApi.register({ phone, nickname: $('#nickname').value.trim(), password, sms_code: smsCode })
        setState('注册成功，正在进入个人中心。')
        location.replace(returnTarget())
        return
      }
      if (mode === 'forgot') {
        await window.jianwenApi.resetPassword(phone, smsCode, password)
        setMode('login')
        $('#phone').value = phone
        setState('密码已重置，请使用新密码登录。')
        return
      }
      await window.jianwenApi.login(phone, password)
      setState('登录成功，正在同步账号数据。')
      location.replace(returnTarget())
    } catch (error) {
      setState(error.message, true)
    } finally {
      submit.disabled = false
    }
  })

  $('#auth-session').hidden = !window.getToken()
  setMode(mode)
})()
