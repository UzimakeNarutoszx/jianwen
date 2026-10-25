const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches

function playIntro() {
  document.querySelectorAll('.intro-page, .intro-page *').forEach(element => {
    element.getAnimations().forEach(animation => {
      animation.cancel()
      animation.play()
    })
  })
}

document.getElementById('intro-replay')?.addEventListener('click', playIntro)

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') location.href = 'index.html?v=20261025-3'
})

if (!reducedMotion && window.tsParticles) {
  tsParticles.load({
    id: 'intro-particles',
    options: {
      fullScreen: { enable: false },
      detectRetina: true,
      fpsLimit: 60,
      particles: {
        color: { value: ['#a9e6e0', '#d4aa4e', '#ffffff'] },
        links: { color: '#a9e6e0', distance: 145, enable: true, opacity: 0.11, width: 1 },
        move: { enable: true, speed: 0.42, direction: 'none', outModes: { default: 'out' } },
        number: { density: { enable: true, width: 1180, height: 780 }, value: 62 },
        opacity: { value: { min: 0.08, max: 0.42 }, animation: { enable: true, speed: 0.35, sync: false } },
        shape: { type: 'circle' },
        size: { value: { min: 1, max: 3 } }
      },
      interactivity: {
        events: { onHover: { enable: true, mode: 'grab' }, resize: { enable: true } },
        modes: { grab: { distance: 175, links: { opacity: 0.28 } } }
      }
    }
  }).catch(() => {})
}
