// Estado de la aplicación
let ws = null;
let currentUser = null;
let currentRoom = null;
let messageCount = 0;
let isConnected = false;

// Elementos DOM
const loginScreen = document.getElementById('login-screen');
const chatScreen = document.getElementById('chat-screen');
const loginForm = document.getElementById('login-form');
const messagesContainer = document.getElementById('messages-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const disconnectBtn = document.getElementById('disconnect-btn');
const roomName = document.getElementById('room-name');
const userBadge = document.getElementById('user-badge');
const connectionStatus = document.getElementById('connection-status');
const messageCountSpan = document.getElementById('message-count');
const errorMessage = document.getElementById('error-message');
const loginSpinner = document.getElementById('login-spinner');

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
    loginForm.addEventListener('submit', handleLogin);
    messageInput.addEventListener('keypress', handleKeyPress);
    sendBtn.addEventListener('click', handleSendMessage);
    disconnectBtn.addEventListener('click', handleDisconnect);
});

// Manejar login
async function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const room = document.getElementById('room').value.trim();
    const host = document.getElementById('server-host').value.trim() || 'localhost';
    const port = document.getElementById('server-port').value || '50051';
    
    if (!username || !room) {
        showError('Usuario y sala son obligatorios');
        return;
    }
    
    loginSpinner.classList.add('show');
    sendBtn.disabled = true;
    errorMessage.classList.remove('show');
    
    try {
        await connectWebSocket(username, room, host, port);
    } catch (error) {
        showError('Error al conectar: ' + error.message);
        loginSpinner.classList.remove('show');
        sendBtn.disabled = false;
    }
}

// Conectar WebSocket
function connectWebSocket(user, room, host, port) {
    return new Promise((resolve, reject) => {
        // Determinar protocolo WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            // Enviar mensaje de inicialización
            ws.send(JSON.stringify({
                type: 'init',
                user: user,
                room: room,
                host: host,
                port: parseInt(port)
            }));
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data, resolve, reject);
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            reject(new Error('Error de conexión WebSocket'));
        };
        
        ws.onclose = () => {
            if (isConnected) {
                handleDisconnect();
            }
        };
    });
}

// Manejar mensajes WebSocket
function handleWebSocketMessage(data, resolve, reject) {
    switch (data.type) {
        case 'joined':
            currentUser = data.user || currentUser;
            currentRoom = data.room || currentRoom;
            isConnected = true;
            
            // Cambiar a pantalla de chat
            loginScreen.classList.remove('active');
            chatScreen.classList.add('active');
            
            // Actualizar UI
            roomName.textContent = `# ${currentRoom}`;
            userBadge.textContent = currentUser;
            updateConnectionStatus(true);
            
            // Limpiar mensaje de bienvenida
            messagesContainer.innerHTML = '';
            
            loginSpinner.classList.remove('show');
            messageInput.disabled = false;
            sendBtn.disabled = false;
            messageInput.focus();
            
            resolve();
            break;
            
        case 'history':
            // Agregar historial
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    addMessage(msg);
                });
            }
            break;
            
        case 'message':
            addMessage(data);
            break;
            
        case 'error':
            showError(data.message);
            reject(new Error(data.message));
            break;
            
        case 'pong':
            // Mantener conexión viva
            break;
    }
}

// Agregar mensaje al chat
function addMessage(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    
    // Determinar tipo de mensaje
    if (data.sender === 'system') {
        messageDiv.className += ' system';
    } else if (data.sender === currentUser) {
        messageDiv.className += ' user';
    } else {
        messageDiv.className += ' other';
    }
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    if (data.sender !== 'system') {
        const messageHeader = document.createElement('div');
        messageHeader.className = 'message-header';
        
        const senderSpan = document.createElement('span');
        senderSpan.className = 'sender';
        senderSpan.textContent = data.sender;
        
        const timestampSpan = document.createElement('span');
        timestampSpan.className = 'timestamp';
        timestampSpan.textContent = formatTimestamp(data.timestamp);
        
        messageHeader.appendChild(senderSpan);
        messageHeader.appendChild(timestampSpan);
        messageDiv.appendChild(messageHeader);
    }
    
    const textP = document.createElement('p');
    textP.textContent = data.text;
    messageContent.appendChild(textP);
    messageDiv.appendChild(messageContent);
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    messageCount++;
    messageCountSpan.textContent = `${messageCount} mensajes`;
}

// Formatear timestamp
function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    // Si es hoy, mostrar solo hora
    if (diff < 86400000) {
        return date.toLocaleTimeString('es-ES', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    // Si es ayer
    if (diff < 172800000) {
        return 'Ayer ' + date.toLocaleTimeString('es-ES', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    // Mostrar fecha completa
    return date.toLocaleString('es-ES', { 
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

// Manejar envío de mensaje
function handleSendMessage() {
    const text = messageInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    
    ws.send(JSON.stringify({
        type: 'message',
        text: text
    }));
    
    messageInput.value = '';
    messageInput.focus();
}

// Manejar tecla Enter
function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
    }
}

// Manejar desconexión
function handleDisconnect() {
    if (ws) {
        ws.close();
        ws = null;
    }
    
    isConnected = false;
    currentUser = null;
    currentRoom = null;
    messageCount = 0;
    
    // Volver a pantalla de login
    chatScreen.classList.remove('active');
    loginScreen.classList.add('active');
    
    // Resetear formulario
    loginForm.reset();
    messagesContainer.innerHTML = '';
    updateConnectionStatus(false);
    messageCountSpan.textContent = '0 mensajes';
    
    messageInput.disabled = true;
    sendBtn.disabled = true;
}

// Actualizar estado de conexión
function updateConnectionStatus(connected) {
    if (connected) {
        connectionStatus.classList.add('connected');
        connectionStatus.innerHTML = '<span class="status-dot"></span> Conectado';
    } else {
        connectionStatus.classList.remove('connected');
        connectionStatus.innerHTML = '<span class="status-dot"></span> Desconectado';
    }
}

// Mostrar error
function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.add('show');
}

// Ping para mantener conexión viva
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
    }
}, 30000); // Cada 30 segundos

