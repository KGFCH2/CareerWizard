
const root = document.documentElement;
const body = document.body;

function toggleTheme(){
  body.classList.toggle('light');
  localStorage.setItem('theme', body.classList.contains('light') ? 'light' : 'dark');
}
window.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('theme');
  if(saved === 'light'){ body.classList.add('light'); }
  // nav active glow
  const current = location.pathname;
  document.querySelectorAll('.nav-links a').forEach(a => {
    if(a.getAttribute('href') === current){ a.classList.add('active'); }
  });
});
