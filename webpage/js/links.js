const groups = document.querySelector('#link-groups')
const grouped = window.portalData.links.reduce((result, item) => {
  ;(result[item.category] ||= []).push(item)
  return result
}, {})

groups.innerHTML = Object.entries(grouped).map(([category, items]) => `
  <section class="link-group">
    <div class="group-heading"><p class="eyebrow">COLLECTION</p><h2>${category}</h2></div>
    <div class="link-list">
      ${items.map(item => `<a class="link-item" href="${item.url}" target="_blank" rel="noopener noreferrer"><span class="link-symbol">↗</span><div><strong>${item.name}</strong><p>${item.description}</p></div><span class="link-arrow">↗</span></a>`).join('')}
    </div>
  </section>
`).join('')
