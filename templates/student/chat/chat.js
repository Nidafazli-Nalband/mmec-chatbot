const userInput = document.getElementById('user-input');
const quickAccessBar = document.getElementById('quick-access-bar');
const aiStatus = document.getElementById('ai-status');
let offlineFAQ = null;
const suggestionsList = document.getElementById('suggestions-list');
const chatInputArea = document.getElementById('chat-input-area');
const messagesContainer = document.getElementById('messages');

// Suggestions data (can be expanded or loaded from server)
const availableQueries = [
  'admission process', 'how to apply for admission', 'required documents for admission',
  'courses offered at mmec', 'fee structure for b.tech', 'scholarships available',
  'placement record', 'top recruiters', 'contact details for admissions', 'hostel facilities',
  'campus facilities', 'student life', 'college website', 'management', 'fee payment', 'results'
];
let selectedSuggestionIndex = -1;

// Utility function to get current time for timestamps
function formatTime() {
const now = new Date();
const hours = now.getHours();
const minutes = now.getMinutes().toString().padStart(2, '0');
const ampm = hours >= 12 ? 'PM' : 'AM';
const formattedHours = (hours % 12 || 12).toString().padStart(2, '0');
return `${formattedHours}:${minutes} ${ampm}`;
}

// Return a locale date+time string
function formatDateTime() {
  return new Date().toLocaleString();
}

// Get last bot message text from the DOM (plain text)
function getLastBotText(){
  try{
    const msgs = document.getElementById('messages');
    if(!msgs) return '';
    const botMsgs = msgs.querySelectorAll('.msg.bot');
    if(!botMsgs || botMsgs.length === 0) return '';
    const last = botMsgs[botMsgs.length - 1];
    return last ? last.textContent || '' : '';
  }catch(e){ return ''; }
}

// Format FAQ answer with emojis and line breaks
function formatAnswerHTML(answer) {
  if (!answer) return '';
  // Replace newlines with <br>
  let formatted = answer.replace(/\n/g, '<br>');
  // Add spacing after emojis (if not present)
  formatted = formatted.replace(/([\u{1F600}-\u{1F64F}\u{2700}-\u{27BF}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}])([^ <])/gu, '$1 $2');
  // Optionally bold first line (title)
  formatted = formatted.replace(/^(.+?)<br>/, '<b>$1</b><br>');
  return formatted;
}

function getDisplayName(){
  return localStorage.getItem('mmec_name') || localStorage.getItem('mmec_user') || localStorage.getItem('mmec_email') || 'Guest';
}

function getUserKey(){
  // canonical user key for server-side storage (prefer email if available)
  return localStorage.getItem('mmec_email') || localStorage.getItem('mmec_user') || 'guest';
}

// Function to find matching FAQ
// findMatchingFAQ: optional threshold param to allow aggressive matching for quick-access
function findMatchingFAQ(query, threshold=0.35) {
    if (!offlineFAQ) return null;

    const queryLower = query.toLowerCase().trim();
  // Token-overlap scoring for more flexible matching
  const stopwords = new Set(['the','is','in','at','of','a','an','and','or','how','what','to','do','for']);
  const qTokens = queryLower.split(/\W+/).filter(t => t && !stopwords.has(t));
  if (qTokens.length === 0) return null;

  let best = {score: 0, answer: null};
  for (const category in offlineFAQ) {
    const faqItem = offlineFAQ[category];
    // check questions
    for (const question of (faqItem.questions || [])) {
      const q = question.toLowerCase();
      const qt = q.split(/\W+/).filter(t => t && !stopwords.has(t));
      // compute overlap
      let common = 0;
      for (const t of qTokens) if (qt.includes(t)) common++;
      const score = common / Math.max(qt.length, qTokens.length);
      if (score > best.score) {
        best.score = score;
        best.answer = faqItem.answer;
      }
      // quick exact containment check
      if (q.includes(queryLower) || queryLower.includes(q)) {
        return faqItem.answer;
      }
    }
    // also check the answer text itself for keywords
    if (faqItem.answer) {
      const ansLower = faqItem.answer.toLowerCase();
      let common = 0;
      for (const t of qTokens) if (ansLower.includes(t)) common++;
      const score = common / Math.max(1, qTokens.length);
      if (score > best.score) {
        best.score = score;
        best.answer = faqItem.answer;
      }
    }
  }
  // threshold for accepting fuzzy match
  return best.score >= threshold ? best.answer : null;
}

async function sendMessage() {
const text = userInput.value.trim();
if (!text) return;

const messagesContainer = document.getElementById('messages');
const currentTime = formatDateTime();
 const token = localStorage.getItem('mmec_token');

// 1. User Message
const msgUser = document.createElement('div');
msgUser.className = 'msg user';
msgUser.innerHTML = `${text}<div class="msg-info">👤 <span>${currentTime}</span></div>`;
messagesContainer.appendChild(msgUser);
userInput.value = '';

// Auto-scroll to bottom
messagesContainer.scrollTop = messagesContainer.scrollHeight;

// Check for offline FAQ match first
let offlineAnswer = null;
// If user asks for a "website link" prefer context from last bot message (VTU vs MMEC)
const websiteQueryRegex = /\b(website link|website|link of the website|give me the website link|website link please|link)\b/i;
if (websiteQueryRegex.test(text)) {
  const lastBot = getLastBotText();
  if (lastBot && /vtu/i.test(lastBot)) {
    offlineAnswer = 'VTU official website: https://vtu.ac.in';
  } else if (lastBot && /(mmec|mmec website|college website|mmec\.edu|mmec\.edu\.in)/i.test(lastBot)) {
    offlineAnswer = 'Visit our website: https://www.mmec.edu.in';
  } else {
    offlineAnswer = findMatchingFAQ(text);
  }
} else {
  offlineAnswer = findMatchingFAQ(text);
}

if (offlineAnswer) {
    // Use offline answer
    const msgBot = document.createElement('div');
    msgBot.className = 'msg bot';
    const formattedAnswer = formatAnswerHTML(offlineAnswer);
    msgBot.innerHTML = `${formattedAnswer}<div class="msg-info">🤖 <span>${formatDateTime()}</span></div>`;
    messagesContainer.appendChild(msgBot);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Use token (declared above) for history and logging

    // Save to history
    await fetch('/api/history', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token
      },
      body: JSON.stringify({
          user: getUserKey(),
        from: 'user',
        text: text,
        ts: new Date().toISOString() + 'Z'
      })
    });

    await fetch('/api/history', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token
      },
      body: JSON.stringify({
          user: getUserKey(),
        // Use offline answer (plain text) for storage
        text: offlineAnswer,
        ts: new Date().toISOString() + 'Z'
      })
    });

    // Log as offline
    await fetch('/api/logs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token
      },
      body: JSON.stringify({
        user: getUserKey(),
        user_msg: text,
        bot_msg: offlineAnswer,
        offline: true
      })
    });

    // Persist this query as a suggestion (most-recent first)
    try{
      if (!availableQueries.includes(text)) availableQueries.unshift(text);
      const saved = JSON.parse(localStorage.getItem('mmec_suggestions')||'[]');
      if (!saved.includes(text)) { saved.unshift(text); localStorage.setItem('mmec_suggestions', JSON.stringify(saved.slice(0,100))); }
    }catch(e){}

    return; // Exit early since we used offline answer
}

// 2. Loading Message (only if not offline)
const loadingMsg = document.createElement('div');
loadingMsg.className = 'msg bot loading';
loadingMsg.innerHTML = `🤖 Thinking...`;
messagesContainer.appendChild(loadingMsg);
messagesContainer.scrollTop = messagesContainer.scrollHeight;

// Reduce delay for faster response
await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 200));

  // Get role and user
  const role = localStorage.getItem('mmec_role') || 'Student';
  const user = getDisplayName();

try {
  const res = await fetch('/api/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Token': token
    },
    body: JSON.stringify({ message: text, role: role })
  });

  // Defensive parsing: server might return HTML on auth error
  const txt = await res.text();
  let data = {};
  try { data = JSON.parse(txt); } catch(e) { data = { error: txt }; }

  // Remove loading message
  messagesContainer.removeChild(loadingMsg);

    if (res.ok) {
    // 3. Bot Reply
    const msgBot = document.createElement('div');
    msgBot.className = 'msg bot';
    let rawAnswer = data.answer || '';
    let formattedAnswer = formatAnswerHTML(rawAnswer);
    // (Removed client-side notice insertion for non-MMEC answers)
    msgBot.innerHTML = `${formattedAnswer}<div class="msg-info">🤖 <span>${formatDateTime()}</span></div>`;
    messagesContainer.appendChild(msgBot);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Save user message to history

    // Save user message to history
    await fetch('/api/history', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token
      },
      body: JSON.stringify({
        user: getUserKey(),
        from: 'user',
        text: text,
        ts: new Date().toISOString() + 'Z'
      })
    });

    // Save bot message to history (store raw text for search/consistency)
    await fetch('/api/history', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token
      },
      body: JSON.stringify({
        user: getUserKey(),
        from: 'bot',
        text: rawAnswer,
        ts: new Date().toISOString() + 'Z'
      })
    });

    // Log
    await fetch('/api/logs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token
      },
      body: JSON.stringify({
        user: getUserKey(),
        user_msg: text,
        bot_msg: data.answer,
        offline: false
      })
    });
    // Persist this query as a suggestion (most-recent first)
    try{
      if (!availableQueries.includes(text)) availableQueries.unshift(text);
      const saved = JSON.parse(localStorage.getItem('mmec_suggestions')||'[]');
      if (!saved.includes(text)) { saved.unshift(text); localStorage.setItem('mmec_suggestions', JSON.stringify(saved.slice(0,100))); }
    }catch(e){}
  } else {
    const msgError = document.createElement('div');
    msgError.className = 'msg bot';
    // If server returned HTML, include a short message instead of raw HTML
    const errMsg = data.error || (typeof data === 'string' ? data : 'Unable to process query');
    msgError.innerHTML = `Error: ${errMsg}`;
    messagesContainer.appendChild(msgError);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
} catch (err) {
  // Remove loading message
  if (loadingMsg.parentNode) messagesContainer.removeChild(loadingMsg);
  const msgError = document.createElement('div');
  msgError.className = 'msg bot';
  msgError.innerHTML = `Network error. Please try again.`;
  messagesContainer.appendChild(msgError);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
}

// Load AI status on page load
async function loadAIStatus() {
  const token = localStorage.getItem('mmec_token');
  if (aiStatus) aiStatus.textContent = 'AI Status: Checking...';
  try {
    const res = await fetch('/api/status', { headers: token ? {'X-Session-Token': token} : {} });
    const txt = await res.text();
    let data = {};
    try { data = JSON.parse(txt); } catch(e) { data = {}; }
    if (data.allow_external_queries) {
      if (aiStatus) { aiStatus.textContent = 'AI Enabled'; aiStatus.style.color = '#10b981'; }
    } else {
      if (aiStatus) { aiStatus.textContent = 'AI Disabled'; aiStatus.style.color = '#ef4444'; }
    }
  } catch (e) {
    // Check internet connectivity
    if (navigator.onLine) {
      if (aiStatus) { aiStatus.textContent = 'AI Offline'; aiStatus.style.color = '#f59e0b'; }
    } else {
      if (aiStatus) { aiStatus.textContent = 'No Internet'; aiStatus.style.color = '#ef4444'; }
    }
  }
}

let currentHistoryPage = 1;

// Placeholder functions (Implement these in your main dashboard application logic)
function showHistory() {
  // Load and display chat history
  currentHistoryPage = 1;
  loadChatHistory();
}
function showHome() { window.location.href = '/student/dashboard'; }
function logout() {
  localStorage.removeItem('mmec_token');
  localStorage.removeItem('mmec_user');
  localStorage.removeItem('mmec_role');
  // Clear any client-side chat caches so returning users don't see old messages
  localStorage.removeItem('chat_history');
  localStorage.removeItem('chat_logs');
  // Clear messages DOM so chat is empty immediately
  try{
    const msgs = document.getElementById('messages');
    if (msgs) msgs.innerHTML = '';
    const histModal = document.getElementById('history-modal'); if (histModal) histModal.style.display='none';
  }catch(e){}
  // Return to student dashboard when logging out from chat
  window.location.href = '/student/dashboard';
}

async function loadChatHistory() {
  const messagesContainer = document.getElementById('messages');
  const token = localStorage.getItem('mmec_token');
  const user = getUserKey();

  try {
    const res = await fetch(`/api/history?user=${encodeURIComponent(user)}&page=${currentHistoryPage}&size=50`, { headers: token ? {'X-Session-Token': token} : {} });
    const txt = await res.text();
    let data = {};
    try { data = JSON.parse(txt); } catch(e) { data = { ok: false, history: [] }; }
    if (data.ok && data.history) {
      if (currentHistoryPage === 1) {
        // Clear current messages for first load
        messagesContainer.innerHTML = '<div style="text-align: center; padding: 10px 0;"><button onclick="loadEarlierMessages()" class="load-messages-btn">Load earlier messages</button></div>';
      } else {
        // Remove the load button temporarily
        const loadBtn = messagesContainer.querySelector('.load-messages-btn');
        if (loadBtn) loadBtn.remove();
      }
      // Add history messages
      data.history.reverse().forEach(item => {
        const msg = document.createElement('div');
        const formattedText = (item.text || '').replace(/\n/g, '<br/>');
        msg.className = `msg ${item.from === 'user' ? 'user' : 'bot'}`;
        const time = item.ts ? new Date(item.ts).toLocaleDateString() + ' ' + new Date(item.ts).toLocaleTimeString() : '';
        msg.innerHTML = `${formattedText}<div class="msg-info">${item.from === 'user' ? '👤' : '🤖'} <span>${time}</span></div>`;
        // Insert at the top for earlier messages
        if (currentHistoryPage === 1) {
          messagesContainer.appendChild(msg);
        } else {
          messagesContainer.insertBefore(msg, messagesContainer.firstChild);
        }
      });increase
      // Re-add the load button at the top if more messages available
      if (data.history.length === 50) {
        const loadBtn = document.createElement('div');
        loadBtn.style.textAlign = 'center';
        loadBtn.style.padding = '10px 0';
        loadBtn.innerHTML = '<button onclick="loadEarlierMessages()" class="load-messages-btn">Load earlier messages</button>';
        messagesContainer.insertBefore(loadBtn, messagesContainer.firstChild);
      }
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  } catch (e) {
    console.error('Error loading history', e);
  }
}

  async function deleteHistoryItem(user, ts){
    const token = localStorage.getItem('mmec_token');
    try{
      const res = await fetch('/api/history', { method: 'DELETE', headers: { 'Content-Type': 'application/json', 'X-Session-Token': token }, body: JSON.stringify({ user, ts }) });
      const j = await res.json();
      return !!j.ok;
    }catch(e){ console.error('deleteHistoryItem error', e); return false; }
  }

function loadEarlierMessages() {
  currentHistoryPage++;
  loadChatHistory();
}
// Load offline FAQ on page load
async function loadOfflineFAQ() {
  try {
    const res = await fetch('/api/offline_faq');
    const txt = await res.text();
    try {
      const data = JSON.parse(txt);
      if (data.ok) offlineFAQ = data.faq;
    } catch (e) {
      console.warn('offline_faq parse failed, server response:', txt ? txt.slice(0,200) : '');
    }
  } catch (e) {
    console.error('Error loading offline FAQ:', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // header buttons
  const logoutBtnHeader = document.getElementById('logout-btn');
  if (logoutBtnHeader) logoutBtnHeader.addEventListener('click', ()=> logout());
  const historyBtn = document.getElementById('history-btn');
  if (historyBtn) historyBtn.addEventListener('click', ()=> { document.getElementById('history-modal').style.display='flex'; loadHistoryModal(); });
  // --- Quick Access Button Functionality ---  
  const quickBtns = document.querySelectorAll('.quick-btn');  
  quickBtns.forEach(btn => {  
    const link = btn.getAttribute('data-link');  
    if (link) {  
      btn.addEventListener('click', () => window.open(link, '_blank'));  
      btn.style.cursor = 'pointer';  
      btn.title = 'Open in new tab';  
    } else {  
      btn.addEventListener('click', async () => {  
        const query = btn.getAttribute('data-query');  
        if (!query) return;  
        // aggressive offline FAQ match for quick access (lower threshold)  
        const offlineAnswer = findMatchingFAQ(query, 0.15);  
        if (offlineAnswer) {  
          const messages = document.getElementById('messages');  
          const time = formatDateTime();
          // Remove all current messages before showing quick access response  
          messages.innerHTML = '';  
          // display user message and immediate bot reply  
          const userMsg = document.createElement('div');  
          userMsg.className = 'msg user';  
          userMsg.innerHTML = `${query}<div class="msg-info">👤 <span>${time}</span></div>`;  
          messages.appendChild(userMsg);  
          const botMsg = document.createElement('div');
          botMsg.className = 'msg bot';
          botMsg.innerHTML = `${formatAnswerHTML(offlineAnswer)}<div class="msg-info">🤖 <span>${formatDateTime()}</span></div>`;  
          messages.appendChild(botMsg);  
          messages.scrollTop = messages.scrollHeight;  
          // save to history/logs (best-effort)  
          const token = localStorage.getItem('mmec_token');  
          await fetch('/api/history', { method: 'POST', headers: { 'Content-Type':'application/json','X-Session-Token': token }, body: JSON.stringify({ user: getUserKey(), from:'user', text: query, ts: new Date().toISOString()+'Z' }) }).catch(()=>{});  
          await fetch('/api/history', { method: 'POST', headers: { 'Content-Type':'application/json','X-Session-Token': token }, body: JSON.stringify({ user: getUserKey(), from:'bot', text: offlineAnswer, ts: new Date().toISOString()+'Z' }) }).catch(()=>{});  
          await fetch('/api/logs', { method:'POST', headers:{ 'Content-Type':'application/json','X-Session-Token': token }, body: JSON.stringify({ user: getUserKey(), user_msg: query, bot_msg: offlineAnswer, offline:true }) }).catch(()=>{});  
        } else {  
          // fallback to normal send flow  
          userInput.value = query;  
          // hide suggestions and remove focused state before sending
          if (suggestionsList) { suggestionsList.classList.remove('active'); suggestionsList.style.display = 'none'; }
          chatInputArea && chatInputArea.classList.remove('focused');
          setTimeout(()=> sendMessage(), 150);  
        }  
      });  
    }  
  });

  // Suggestion input handling
  if (userInput) {

  // Drag-to-scroll support for quick access bar
  const quickBar = document.getElementById('quick-access-bar');
  if (quickBar) {
    let isDown = false, startX, scrollLeft;
    quickBar.addEventListener('mousedown', (e)=>{
      isDown = true; quickBar.classList.add('active'); startX = e.pageX - quickBar.offsetLeft; scrollLeft = quickBar.scrollLeft;
      e.preventDefault();
    });
    quickBar.addEventListener('mouseleave', ()=>{ isDown = false; quickBar.classList.remove('active'); });
    quickBar.addEventListener('mouseup', ()=>{ isDown = false; quickBar.classList.remove('active'); });
    quickBar.addEventListener('mousemove', (e)=>{
      if (!isDown) return; e.preventDefault(); const x = e.pageX - quickBar.offsetLeft; const walk = (x - startX) * 1.5; quickBar.scrollLeft = scrollLeft - walk;
    });
    // touch events
    quickBar.addEventListener('touchstart',(e)=>{ startX = e.touches[0].pageX - quickBar.offsetLeft; scrollLeft = quickBar.scrollLeft; });
    quickBar.addEventListener('touchmove',(e)=>{ const x = e.touches[0].pageX - quickBar.offsetLeft; const walk = (x - startX) * 1.5; quickBar.scrollLeft = scrollLeft - walk; });
  }
    userInput.addEventListener('input', handleSuggestionInput);
    userInput.addEventListener('focus', () => chatInputArea && chatInputArea.classList.add('focused'));
    userInput.addEventListener('blur', () => setTimeout(()=>{ if (!suggestionsList.classList.contains('active')) chatInputArea && chatInputArea.classList.remove('focused'); }, 120));

    // Hide suggestion bar when input is empty or not focused
    userInput.addEventListener('input', () => {
      if (!userInput.value.trim()) {
        suggestionsList.style.display = 'none';
      } else {
        suggestionsList.style.display = '';
      }
    });
    userInput.addEventListener('blur', () => {
      suggestionsList.style.display = 'none';
    });
    userInput.addEventListener('focus', () => {
      if (userInput.value.trim()) suggestionsList.style.display = '';
    });

    // AI status button logic
    function setAIStatus(enabled) {
      const aiBtn = document.getElementById('ai-status-btn');
      if (!aiBtn) return;
      if (enabled) {
        aiBtn.textContent = 'AI Enabled';
        aiBtn.classList.remove('disabled');
        aiBtn.classList.add('enabled');
      } else {
        aiBtn.textContent = 'AI Disabled';
        aiBtn.classList.remove('enabled');
        aiBtn.classList.add('disabled');
      }
    }

    // Keyboard navigation for suggestions
    userInput.addEventListener('keydown', (e) => {
      const items = suggestionsList ? suggestionsList.querySelectorAll('.suggestion-item') : [];
      if (!items || items.length === 0) {
        if (e.key === 'Enter') { e.preventDefault();
          // hide suggestions and send
          if (suggestionsList) { suggestionsList.classList.remove('active'); suggestionsList.style.display = 'none'; }
          chatInputArea && chatInputArea.classList.remove('focused');
          sendMessage();
        }
        return;
      }
      if (e.key === 'ArrowDown') { e.preventDefault(); selectedSuggestionIndex = (selectedSuggestionIndex + 1) % items.length; updateSelection(items); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); selectedSuggestionIndex = (selectedSuggestionIndex - 1 + items.length) % items.length; updateSelection(items); }
      else if (e.key === 'Enter') { e.preventDefault();
        if (selectedSuggestionIndex > -1) {
          const sel = items[selectedSuggestionIndex].querySelector('span');
          const text = sel ? sel.textContent : items[selectedSuggestionIndex].textContent;
          selectSuggestion(text);
          // hide suggestions after selecting via keyboard
          if (suggestionsList) { suggestionsList.classList.remove('active'); suggestionsList.style.display = 'none'; }
          chatInputArea && chatInputArea.classList.remove('focused');
          sendMessage();
        } else {
          if (suggestionsList) { suggestionsList.classList.remove('active'); suggestionsList.style.display = 'none'; }
          chatInputArea && chatInputArea.classList.remove('focused');
          sendMessage();
        }
      }
    });
  }

    // Enable send button to send message
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
    sendBtn.addEventListener('click', function() {
    sendMessage();
    });
    }

    loadAIStatus();
    loadOfflineFAQ();

    // Load saved suggestions from localStorage (persisted user queries)
    try{
      const saved = JSON.parse(localStorage.getItem('mmec_suggestions') || '[]');
      if (Array.isArray(saved)){
        saved.reverse().forEach(s=>{ if (!availableQueries.includes(s)) availableQueries.unshift(s); });
      }
    }catch(e){}

    // Instead of auto-loading history, show a 'Load earlier messages' control.
    const messages = document.getElementById('messages');
    if (messages && messages.children.length === 0) {
      // Instead of showing Load Earlier button, directly show greeting message
      const welcome = document.createElement('div');
      welcome.className = 'msg bot';
      welcome.innerHTML = `Hello! 👋 How can I help you with MMEC information today?<div class="msg-info">🤖 <span>${formatDateTime()}</span></div>`;
      messages.appendChild(welcome);
      messages.scrollTop = messages.scrollHeight;
    }
});

// Suggestion helpers
function handleSuggestionInput(){
  if (!suggestionsList) return;
  const query = (userInput.value || '').trim().toLowerCase();
  suggestionsList.innerHTML = '';
  suggestionsList.classList.remove('active');
  selectedSuggestionIndex = -1;
  if (query.length < 2) return;
  const filtered = availableQueries.filter(q => q.toLowerCase().includes(query)).slice(0,8);
  if (filtered.length === 0) return;
  filtered.forEach((s, idx) => {
    const li = document.createElement('li');
    li.className = 'suggestion-item';
    // text
    const span = document.createElement('span');
    span.textContent = s;
    span.style.cursor = 'pointer';
    span.addEventListener('click', ()=> selectSuggestion(s));
    li.appendChild(span);
    // remove button
    const rem = document.createElement('button');
    rem.textContent = '✕';
    rem.title = 'Remove suggestion';
    rem.style.marginLeft = '8px';
    rem.style.background = 'transparent';
    rem.style.border = 'none';
    rem.style.cursor = 'pointer';
    rem.style.color = '#ef4444';
    rem.addEventListener('click', (ev)=>{
      ev.stopPropagation();
      // remove from availableQueries and persisted storage
      const idxIn = availableQueries.findIndex(x=>x===s);
      if (idxIn > -1) availableQueries.splice(idxIn,1);
      try{
        const saved = JSON.parse(localStorage.getItem('mmec_suggestions')||'[]');
        const i2 = saved.indexOf(s);
        if (i2 > -1) { saved.splice(i2,1); localStorage.setItem('mmec_suggestions', JSON.stringify(saved)); }
      }catch(e){}
      li.remove();
    });
    li.appendChild(rem);
    suggestionsList.appendChild(li);
  });
  suggestionsList.classList.add('active');
  chatInputArea && chatInputArea.classList.add('focused');
}

function selectSuggestion(text){
  userInput.value = text;
  suggestionsList.classList.remove('active');
  suggestionsList.style.display = 'none';
  chatInputArea && chatInputArea.classList.remove('focused');
  userInput.focus();
}

function updateSelection(items){
  items.forEach((it, i) => {
    it.classList.toggle('selected', i === selectedSuggestionIndex);
    if (i === selectedSuggestionIndex) {
      const sp = it.querySelector('span');
      userInput.value = sp ? sp.textContent : it.textContent;
    }
  });
}

  // Load history into modal (shows full history list with timestamps)
  async function loadHistoryModal(page=1,size=200){
    const body = document.getElementById('history-modal-body');
    body.innerHTML = '<p>Loading...</p>';
    const token = localStorage.getItem('mmec_token');
    const user = getUserKey();
    try{
      const res = await fetch(`/api/history?user=${encodeURIComponent(user)}&page=${page}&size=${size}`, { headers: token ? {'X-Session-Token': token} : {} });
      const txt = await res.text();
      let j = {};
      try { j = JSON.parse(txt); } catch(e) { j = { ok: false }; }
      if(j.ok && j.history){
        const list = document.createElement('div');
        list.style.maxHeight = '60vh';
        list.style.overflow = 'auto';
        // Add clear history button
        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.justifyContent = 'space-between';
        header.style.alignItems = 'center';
        header.style.marginBottom = '8px';
        const title = document.createElement('div');
        title.textContent = 'Conversation History';
        title.style.fontWeight = '600';
        const clearBtn = document.createElement('button');
        clearBtn.className = 'btn';
        clearBtn.textContent = 'Clear History';
        clearBtn.onclick = async ()=>{ if(!confirm('Clear all saved chat history?')) return; await clearHistory(user); await loadHistoryModal(page,size); };
        header.appendChild(title); header.appendChild(clearBtn);
        body.innerHTML = '';
        body.appendChild(header);
        j.history.reverse().forEach(item=>{
          const row = document.createElement('div');
          row.style.borderBottom = '1px solid #eee';
          row.style.padding = '8px 0';
          const time = item.ts ? new Date(item.ts).toLocaleString() : '';
          row.innerHTML = `<div style="font-size:12px;color:#666">${item.from.toUpperCase()} • ${time}</div><div style="margin-top:6px">${item.text.replace(/\n/g,'<br/>')}</div>`;
          // Load into chat button
          const loadBtn = document.createElement('button');
          loadBtn.textContent = 'Load into Chat';
          loadBtn.className = 'btn';
          loadBtn.style.marginTop = '8px';
          loadBtn.onclick = ()=>{
            addHistoryToChat(item);
            document.getElementById('history-modal').style.display='none';
          };
          // Delete button for this history item (delete by ts)
          const delBtn = document.createElement('button');
          delBtn.textContent = 'Delete';
          delBtn.className = 'btn';
          delBtn.style.marginTop = '8px';
          delBtn.style.marginLeft = '8px';
          delBtn.onclick = async ()=>{
            if(!confirm('Delete this history message?')) return;
            const ok = await deleteHistoryItem(user, item.ts);
            if(ok) await loadHistoryModal(page,size);
            else alert('Delete failed');
          };
          row.appendChild(loadBtn);
          row.appendChild(delBtn);
          list.appendChild(row);
        });
        body.appendChild(list);
      } else {
        body.innerHTML = '<p>No history found.</p>';
      }
    }catch(e){ body.innerHTML = '<p>Error loading history.</p>'; }
  }

// Clear history for a user (DELETE /api/history)
async function clearHistory(user){
  const token = localStorage.getItem('mmec_token');
  try{
    await fetch('/api/history', { method: 'DELETE', headers: { 'Content-Type': 'application/json', 'X-Session-Token': token }, body: JSON.stringify({ user }) });
    return true;
  }catch(e){ console.error('clearHistory error', e); return false; }
}

  function addHistoryToChat(item){
    const messagesContainer = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `msg ${item.from==='user'?'user':'bot'}`;
    const time = item.ts ? new Date(item.ts).toLocaleString() : formatDateTime();
    div.innerHTML = `${item.text.replace(/\n/g,'<br/>')}<div class="msg-info">${item.from==='user'?'👤':'🤖'} <span>${time}</span></div>`;
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
