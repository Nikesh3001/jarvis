class CyberConsole {
    constructor() {
        this.output = document.getElementById('output');
        this.input = document.getElementById('command-input');
        this.history = [];
        this.historyIndex = -1;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.commandQueue = [];
        this.isProcessing = false;
        this.apiKey = this.getApiKey();
        
        this.init();
    }
    
    getApiKey() {
        return document.getElementById('api-key-input')?.value?.trim() || '';
    }
    
    init() {
        this.bindEvents();
        this.connect();
        this.input.focus();
        const keyInput = document.getElementById('api-key-input');
        if (keyInput) {
            keyInput.addEventListener('change', () => {
                this.apiKey = keyInput.value.trim();
            });
        }
    }
    
    bindEvents() {
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        document.getElementById('clear-btn').addEventListener('click', () => this.clear());
        document.getElementById('help-btn').addEventListener('click', () => this.showHelp());
        document.getElementById('close-help').addEventListener('click', () => this.hideHelp());
        document.getElementById('help-modal').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) this.hideHelp();
        });
        
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hideHelp();
            if (e.ctrlKey && e.key === 'l') {
                e.preventDefault();
                this.clear();
            }
        });
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/cyber`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            this.updateStatus('Connected', 'success');
            this.flushQueue();
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            this.updateStatus('Disconnected', 'error');
            this.attemptReconnect();
        };
        
        this.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            this.updateStatus('Connection error', 'error');
        };
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.updateStatus('Max retries reached', 'error');
            return;
        }
        
        this.reconnectAttempts++;
        this.updateStatus(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
        
        setTimeout(() => this.connect(), 2000 * this.reconnectAttempts);
    }
    
    flushQueue() {
        while (this.commandQueue.length > 0) {
            const cmd = this.commandQueue.shift();
            this.sendCommand(cmd);
        }
    }
    
    sendCommand(command) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.commandQueue.push(command);
            return;
        }
        
        this.ws.send(JSON.stringify({ command, api_key: this.apiKey }));
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'output':
                this.appendOutput(data.content, data.class || 'output-text');
                break;
            case 'prompt':
                this.showPrompt();
                break;
            case 'error':
                this.appendOutput(data.content, 'output-error');
                break;
            case 'clear':
                this.clear();
                break;
            case 'banner':
                this.appendOutput(data.content, 'output-banner');
                break;
        }
    }
    
    handleKeydown(e) {
        switch (e.key) {
            case 'Enter':
                e.preventDefault();
                this.executeCommand();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.navigateHistory(-1);
                break;
            case 'ArrowDown':
                e.preventDefault();
                this.navigateHistory(1);
                break;
            case 'Tab':
                e.preventDefault();
                this.autoComplete();
                break;
            case 'c':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.sendInterrupt();
                }
                break;
        }
    }
    
    executeCommand() {
        const command = this.input.value.trim();
        if (!command) return;
        
        this.history.push(command);
        this.historyIndex = this.history.length;
        this.input.value = '';
        
        this.appendOutput(`cyber> ${command}`, 'output-command');
        this.sendCommand(command);
        this.isProcessing = true;
        this.updateStatus('Processing...', 'warning');
    }
    
    navigateHistory(direction) {
        if (this.history.length === 0) return;
        
        this.historyIndex = Math.max(0, Math.min(this.history.length - 1, this.historyIndex + direction));
        this.input.value = this.history[this.historyIndex] || '';
    }
    
    autoComplete() {
        const commands = [
            'nmap', 'shodan', 'shodan-host', 'dns', 'subdomain', 'whois', 'banner', 'traceroute',
            'nikto', 'sqlmap', 'hydra', 'gobuster', 'ffuf',
            'headers', 'ssl', 'jina', 'semantic',
            'firewall', 'ports', 'services', 'listeners', 'updates', 'best-practices',
            'ssh', 'hash', 'hash-id',
            'msf', 'msfvenom', 'msf-script', 'msf-db',
            'git', 'python', 'pip',
            'report', 'tools', 'check', 'help', 'quit', 'exit', 'clear'
        ];
        
        const current = this.input.value.toLowerCase();
        const matches = commands.filter(c => c.startsWith(current));
        
        if (matches.length === 1) {
            this.input.value = matches[0] + ' ';
        } else if (matches.length > 1) {
            this.appendOutput(matches.join('  '), 'output-text');
        }
    }
    
    sendInterrupt() {
        this.sendCommand('\x03');
        this.appendOutput('^C', 'output-warning');
        this.showPrompt();
    }
    
    appendOutput(text, className = 'output-text') {
        const line = document.createElement('div');
        line.className = `line ${className}`;
        line.textContent = text;
        this.output.appendChild(line);
        this.scrollToBottom();
    }
    
    showPrompt() {
        this.isProcessing = false;
        this.updateStatus('Ready', 'success');
        this.input.focus();
    }
    
    updateStatus(text, type) {
        const statusEl = document.querySelector('.status');
        statusEl.textContent = `● ${text}`;
        statusEl.className = `status ${type}`;
    }
    
    scrollToBottom() {
        this.output.scrollTop = this.output.scrollHeight;
    }
    
    clear() {
        this.output.innerHTML = '';
    }
    
    showHelp() {
        document.getElementById('help-modal').classList.remove('hidden');
    }
    
    hideHelp() {
        document.getElementById('help-modal').classList.add('hidden');
        this.input.focus();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new CyberConsole();
});