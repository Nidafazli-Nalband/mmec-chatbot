// Utility function to get current time for timestamps
function formatTime() {
const now = new Date();
const hours = now.getHours();
const minutes = now.getMinutes().toString().padStart(2, '0');
const ampm = hours >= 12 ? 'PM' : 'AM';
const formattedHours = (hours % 12 || 12).toString().padStart(2, '0');
return `${formattedHours}:${minutes} ${ampm}`;
}

async function sendMessage(){
const input = document.getElementById('user-input');
const text = input.value.trim();
if(!text) return;

const messages = document.getElementById('messages');

// User message
const msgUser = document.createElement('div');
msgUser.className = 'msg user';
msgUser.innerHTML = `${text}<div class="msg-info">👤 <span>${formatTime()}</span></div>`;
messages.appendChild(msgUser);
input.value = '';
messages.scrollTop = messages.scrollHeight;

// Get role and token
const role = localStorage.getItem('mmec_role') || 'Student';
const token = localStorage.getItem('mmec_token');

try {
  const res = await fetch('/api/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Token': token
    },
    body: JSON.stringify({ message: text, role: role })
  });

  const data = await res.json();

  if (res.ok) {
    // Bot message
    const msgBot = document.createElement('div');
    msgBot.className = 'msg bot';
    const formattedAnswer = data.answer.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" style="color: #1a73e8; text-decoration: underline;">$1</a>');
    msgBot.innerHTML = `${formattedAnswer}<div class="msg-info">🤖 <span>${formatTime()}</span></div>`;
    messages.appendChild(msgBot);
    messages.scrollTop = messages.scrollHeight;

    // Save to history
    await fetch('/api/history', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token
      },
      body: JSON.stringify({
        user: localStorage.getItem('mmec_user'),
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
        user: localStorage.getItem('mmec_user'),
        from: 'bot',
        text: formattedAnswer,
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
        user_msg: text,
        bot_msg: data.answer,
        offline: false
      })
    });
  } else {
    const msgError = document.createElement('div');
    msgError.className = 'msg bot';
    msgError.innerHTML = `Error: ${data.error || 'Unable to process query'}<div class="msg-info">🤖 <span>${formatTime()}</span></div>`;
    messages.appendChild(msgError);
    messages.scrollTop = messages.scrollHeight;
  }
} catch (err) {
  const msgError = document.createElement('div');
  msgError.className = 'msg bot';
  msgError.innerHTML = `Network error. Please try again.<div class="msg-info">🤖 <span>${formatTime()}</span></div>`;
  messages.appendChild(msgError);
  messages.scrollTop = messages.scrollHeight;
}
}

// Enable Enter key to send message
const userInput = document.getElementById('user-input');
if (userInput) {
userInput.addEventListener("keypress", function(e) {
if (e.key === "Enter") {
e.preventDefault();
sendMessage();
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

// Load AI status on page load
async function loadAIStatus() {
  const token = localStorage.getItem('mmec_token');
  const aiStatus = document.getElementById('ai-status');
  if (aiStatus) {
    aiStatus.textContent = 'AI Status: Checking...';
    try {
      const res = await fetch('/api/status', {
        headers: token ? {'X-Session-Token': token} : {}
      });
      const data = await res.json();
      if (data.allow_external_queries) {
        aiStatus.textContent = 'AI Enabled';
        aiStatus.style.color = '#10b981'; // Green for enabled
      } else {
        aiStatus.textContent = 'AI Disabled';
        aiStatus.style.color = '#ef4444'; // Red for disabled
      }
    } catch (e) {
      // Check internet connectivity
      if (navigator.onLine) {
        aiStatus.textContent = 'AI Offline';
        aiStatus.style.color = '#f59e0b'; // Orange for offline
      } else {
        aiStatus.textContent = 'No Internet';
        aiStatus.style.color = '#ef4444'; // Red for no internet
      }
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
  window.location.href = '/student/dashboard';
}

async function loadChatHistory() {
  const messagesContainer = document.getElementById('messages');
  const token = localStorage.getItem('mmec_token');
  const user = localStorage.getItem('mmec_user') || 'guest';

  try {
    const res = await fetch(`/api/history?user=${encodeURIComponent(user)}&page=${currentHistoryPage}&size=50`, {
      headers: token ? {'X-Session-Token': token} : {}
    });
    const data = await res.json();
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
        msg.className = `msg ${item.from === 'user' ? 'user' : 'bot'}`;
        const time = item.ts ? new Date(item.ts).toLocaleTimeString() : '';
        const formattedText = item.text.replace(/\n/g, '<br>');
        msg.innerHTML = `${formattedText}<div class="msg-info">${item.from === 'user' ? '👤' : '🤖'} <span>${time}</span></div>`;
        // Insert at the top for earlier messages
        if (currentHistoryPage === 1) {
          messagesContainer.appendChild(msg);
        } else {
          messagesContainer.insertBefore(msg, messagesContainer.firstChild);
        }
      });
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

function loadEarlierMessages() {
  currentHistoryPage++;
  loadChatHistory();
}
document.addEventListener('DOMContentLoaded', loadAIStatus);
