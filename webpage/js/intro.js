document.getElementById('intro-replay').addEventListener('click', () => {
  document.querySelectorAll('.intro-page, .intro-page *').forEach(element => {
    element.getAnimations().forEach(animation => { animation.cancel(); animation.play() })
  })
})
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') location.href = 'index.html?v=20260919-6'
})
