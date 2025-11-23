MMEC Chatbot Template Scaffold

This folder contains a simple scaffold with separate HTML/CSS/JS files per page so you can split your single-file app into modular pages.

Structure:
- template/
  - common/ (shared CSS/JS)
  - splash/ (splash screen)
  - login/ (login page)
  - home/ (post-login landing)
  - student/
    - dashboard/ (student dashboard)
    - manage_images/ (image upload page)
    - profile/ (student profile or extra page)
  - admin/ (admin dashboard)
  - chat/ (chat interface)
  - assets/ (images, icons)

How to use:
1. Open the project folder in VS Code.
2. Each page has its own .html, .css and .js file. Edit them separately.
3. To preview locally, run a static server in the template folder. Example (PowerShell):

   # using Python 3.x
   python -m http.server 8000 --directory "template"

   Then open http://localhost:8000/<page_folder>/<page>.html

Next steps you might want:
- Wire a simple backend API (Flask/FastAPI/Express) for /api/* endpoints used by the chat UI.
- Migrate the big inline JS into modular services (auth, chat, kb matcher).
- Add bundling (Vite, webpack) if you plan to use modules and NPM packages.

PROMPT.md contains the chatbot app prompt you supplied, saved for future use.
