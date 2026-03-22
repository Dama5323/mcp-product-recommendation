// src/App.js
import React, { useState, useEffect, useRef } from 'react';
import ChatInterface from './components/ChatInterface';
import LeftSidebar from './components/LeftSidebar';
import RightSidebar from './components/RightSidebar';
import './App.css';

// Cookie utility functions
const setCookie = (name, value, days = 30) => {
  const expires = new Date();
  expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
  document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
};

const getCookie = (name) => {
  const nameEQ = name + "=";
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
  }
  return null;
};

const App = () => {
  // Environment-aware paths
  const isProxy = window.location.pathname.includes('/proxy/');
  const logoPath = isProxy ? '/proxy/3000/aws-logo.png' : './aws-logo.png';
  const homePath = isProxy ? '/proxy/3000/' : '/';

  // Core state
  const [messages, setMessages] = useState([]);
  const [mcpLogs, setMcpLogs] = useState({});
  const [backendStatus, setBackendStatus] = useState('checking');
  const [mcpStatus, setMcpStatus] = useState('checking');
  
  // UI state
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(320);
  const [rightSidebarWidth, setRightSidebarWidth] = useState(350);
  // Initialize selectedModel from cookie or use default
  const [selectedModel, setSelectedModel] = useState(() => {
    const savedModel = getCookie('selectedModel');
    return savedModel || 'global.anthropic.claude-sonnet-4-5-20250929-v1:0';
  });
  const [tokenCount, setTokenCount] = useState(0);
  const [isResizing, setIsResizing] = useState(null);
  
  const leftResizeRef = useRef(null);
  const rightResizeRef = useRef(null);

  // Save selectedModel to cookie whenever it changes
  useEffect(() => {
    setCookie('selectedModel', selectedModel);
    console.log(`Model selection saved to cookie: ${selectedModel}`);
  }, [selectedModel]);

  // Check backend health
  useEffect(() => {
    const checkHealth = async () => {
      try {
            const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
    const response = await fetch(`${apiBase}/health`);
        if (response.ok) {
          setBackendStatus('online');
        } else {
          setBackendStatus('offline');
        }
      } catch (error) {
        setBackendStatus('offline');
      }
    };

    checkHealth();
    const healthInterval = setInterval(checkHealth, 5000);
    return () => clearInterval(healthInterval);
  }, []);

  // Check MCP servers status
  useEffect(() => {
    const checkMcpStatus = async () => {
      try {
            const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
    const response = await fetch(`${apiBase}/mcp/servers`);
        if (response.ok) {
          setMcpStatus('online');
        } else {
          setMcpStatus('offline');
        }
      } catch (error) {
        setMcpStatus('offline');
      }
    };

    checkMcpStatus();
    const mcpInterval = setInterval(checkMcpStatus, 5000);
    return () => clearInterval(mcpInterval);
  }, []);

  // Fetch MCP logs
  useEffect(() => {
    const fetchLogs = async () => {
      try {
            const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
    const response = await fetch(`${apiBase}/mcp/logs`);
        if (response.ok) {
          const logs = await response.json();
          setMcpLogs(logs);
        }
      } catch (error) {
        console.error('Error fetching logs:', error);
      }
    };

    fetchLogs();
    const logsInterval = setInterval(fetchLogs, 2000);
    return () => clearInterval(logsInterval);
  }, []);

  const clearLogs = () => {
    setMcpLogs({});
  };

  // Handle mouse down for resizing
  const handleMouseDown = (side) => (e) => {
    e.preventDefault();
    setIsResizing(side);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  // Handle mouse move for resizing
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;

      if (isResizing === 'left') {
        const newWidth = Math.max(250, Math.min(500, e.clientX));
        setLeftSidebarWidth(newWidth);
      } else if (isResizing === 'right') {
        const newWidth = Math.max(250, Math.min(500, window.innerWidth - e.clientX));
        setRightSidebarWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(null);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const toggleLeftSidebar = () => {
    setLeftSidebarOpen(!leftSidebarOpen);
  };

  const toggleRightSidebar = () => {
    setRightSidebarOpen(!rightSidebarOpen);
  };

  // Register global functions for sidebar components
  useEffect(() => {
    window.toggleLeftSidebar = toggleLeftSidebar;
    window.toggleRightSidebar = toggleRightSidebar;
    
    return () => {
      delete window.toggleLeftSidebar;
      delete window.toggleRightSidebar;
    };
  }, [leftSidebarOpen, rightSidebarOpen, toggleLeftSidebar, toggleRightSidebar]);

  return (
    <div className="app">
      {/* Simplified Header */}
      <header className="app-header">
        <div className="header-left">
          <button 
            className="sidebar-toggle" 
            onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
          >
            {leftSidebarOpen ? '◀' : '▶'}
          </button>
          <div 
            className="app-logo" 
            onClick={() => window.location.href = homePath}
            style={{ cursor: 'pointer' }}
          >
            <img src={logoPath} alt="AWS" className="aws-logo" />
            <div className="app-title">
              <span className="title-main">Productivity Accelerators</span>
              <span className="title-sub">POWERED BY AWS & STRANDS</span>
            </div>
          </div>
        </div>
        
        <div className="header-right">
          <button 
            className="sidebar-toggle" 
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
          >
            {rightSidebarOpen ? '▶' : '◀'}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {/* Left Sidebar */}
        <div 
          className={`sidebar-container left ${!leftSidebarOpen ? 'closed' : ''}`}
          style={{ width: leftSidebarOpen ? `${leftSidebarWidth}px` : '0' }}
        >
          <LeftSidebar 
            isOpen={leftSidebarOpen}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
          />
          {leftSidebarOpen && (
            <div 
              className="resize-handle left"
              onMouseDown={handleMouseDown('left')}
              ref={leftResizeRef}
            />
          )}
        </div>

        {/* Chat Interface */}
        <div className="chat-container">
          <ChatInterface 
            messages={messages}
            setMessages={setMessages}
            selectedModel={selectedModel}
            tokenCount={tokenCount}
            setTokenCount={setTokenCount}
            leftSidebarOpen={leftSidebarOpen}
            rightSidebarOpen={rightSidebarOpen}
            toggleLeftSidebar={toggleLeftSidebar}
            toggleRightSidebar={toggleRightSidebar}
          />
        </div>

        {/* Right Sidebar */}
        <div 
          className={`sidebar-container right ${!rightSidebarOpen ? 'closed' : ''}`}
          style={{ width: rightSidebarOpen ? `${rightSidebarWidth}px` : '0' }}
        >
          {rightSidebarOpen && (
            <div 
              className="resize-handle right"
              onMouseDown={handleMouseDown('right')}
              ref={rightResizeRef}
            />
          )}
          <RightSidebar 
            isOpen={rightSidebarOpen}
            logs={mcpLogs}
            clearLogs={clearLogs}
          />
        </div>
      </main>
    </div>
  );
};

export default App;