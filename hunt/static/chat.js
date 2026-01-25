// Chat functionality for level pages
(function() {
  'use strict';

  const levelNumber = document.body.dataset.levelNumber;
  if (!levelNumber) return;

  // Cache DOM elements
  const elements = {
    messages: document.getElementById('chat-messages'),
    messageInput: document.getElementById('chat-message-input'),
    messageSubmit: document.getElementById('chat-message-submit'),
    usernameInput: document.getElementById('username-input'),
    usernameSubmit: document.getElementById('username-submit'),
    usernameDisplay: document.getElementById('username-display'),
    chat: document.getElementById('chat'),
    username: document.getElementById('username')
  };

  let userName = '';

  // WebSocket setup
  const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const chatSocket = new WebSocket(
    wsScheme + '://' + window.location.host + '/level/' + levelNumber + '/'
  );

  chatSocket.onopen = function() {
    console.log('Chat connected');
  };

  chatSocket.onclose = function() {
    console.error('Chat disconnected unexpectedly');
  };

  chatSocket.onerror = function(e) {
    console.error('Chat error:', e);
  };

  chatSocket.onmessage = function(e) {
    const data = JSON.parse(e.data);

    const name = document.createElement('b');
    name.textContent = data.username;

    const message = document.createTextNode(': ' + data.message);
    const linebreak = document.createElement('br');

    elements.messages.appendChild(name);
    elements.messages.appendChild(message);
    elements.messages.appendChild(linebreak);

    scrollToBottom();
  };

  // Event handlers
  elements.messageInput.addEventListener('keyup', function(e) {
    if (e.key === 'Enter') {
      elements.messageSubmit.click();
    }
  });

  elements.usernameInput.addEventListener('keyup', function(e) {
    if (e.key === 'Enter') {
      elements.usernameSubmit.click();
    }
  });

  elements.messageSubmit.addEventListener('click', function() {
    const message = elements.messageInput.value;

    if (message && chatSocket.readyState === WebSocket.OPEN) {
      chatSocket.send(JSON.stringify({
        message: message,
        username: userName
      }));
    }

    elements.messageInput.value = '';
  });

  elements.usernameSubmit.addEventListener('click', function() {
    const value = elements.usernameInput.value;
    if (value.length === 0 || value.length > 32) {
      return;
    }
    userName = value;
    elements.chat.removeAttribute('hidden');
    elements.username.setAttribute('hidden', true);
    elements.usernameDisplay.textContent = 'Your username: ' + userName;
    elements.messageInput.focus();
  });

  function scrollToBottom() {
    elements.messages.scrollTop = elements.messages.scrollHeight;
  }

  // Initial scroll
  scrollToBottom();
})();
