// Common JS helpers for the scaffold
function qs(sel, root=document){return root.querySelector(sel)}
function qsa(sel, root=document){return Array.from(root.querySelectorAll(sel))}
function show(el){if(!el) return; el.style.display=''}
function hide(el){if(!el) return; el.style.display='none'}
function setText(el, t){ if(!el) return; el.textContent = t }
// simple DOM ready
function ready(fn){ if(document.readyState!='loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

// Inject a shared one-line topbar across pages for quick access navigation.
ready(() => {
	try {
		// Don't inject on login or register pages
		const path = window.location.pathname || '/';
		if (path.startsWith('/login') || path.startsWith('/register')) return;

		// If a topbar already exists, do nothing
		if (document.querySelector('.site-topbar')) return;

		const topbar = document.createElement('div');
		topbar.className = 'site-topbar';

		// Render extended quick-access only on splash and chat pages
		const links = `
			<div class="container topbar-inner">
				<div class="topbar-left"><a class="topbar-brand" href="/">MMEC</a></div>
				<nav class="topbar-nav" role="navigation" aria-label="Primary">
					<a href="/home" class="topbar-link">Home</a>
					<a href="/admissions" class="topbar-link">Admissions</a>
					<a href="/courses" class="topbar-link">Courses</a>
					<a href="/facilities" class="topbar-link">Facilities</a>
					<a href="/placements" class="topbar-link">Placements</a>
					<a href="/events" class="topbar-link">Events</a>
					<a href="/about" class="topbar-link">About</a>
					<a href="/contact" class="topbar-link">Contact</a>
				</nav>
			</div>
		`;

		topbar.innerHTML = links;

		// Make MMEC brand click return to splash
		topbar.querySelector('.topbar-brand').addEventListener('click', (e) => {
			e.preventDefault();
			window.location.href = '/';
		});

		// Insert at top of body
		document.body.insertBefore(topbar, document.body.firstChild);

		// If pages already have a header with class 'page-header' or nav-links, hide it to avoid duplicates
		const pageHeader = document.querySelector('.page-header');
		if (pageHeader) pageHeader.style.display = 'none';
		const navLinks = document.querySelector('.nav-links');
		if (navLinks) navLinks.style.display = 'none';
	} catch (e) {
		console.error('topbar injection failed', e);
	}
});
