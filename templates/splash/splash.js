// Optional client-side enhancements for the splash page
document.addEventListener('DOMContentLoaded', function(){
  // If user presses Enter, follow Start Chat button
  const btn = document.querySelector('.splash-cta .btn')
  document.addEventListener('keydown', (e)=>{ if(e.key==="Enter") btn && btn.click() })

  // Add navigation for nav links
  const navLinks = document.querySelectorAll('.nav-links a')
  navLinks.forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault()
      const target = this.getAttribute('href')
      window.location.href = target
    })
  })
})
// splash page behavior if needed
ready(()=>{
  // future enhancements (animations, interactions)
});
