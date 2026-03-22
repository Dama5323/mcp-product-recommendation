// src/components/ChatInterface.js
import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './ChatInterface.css';

const ChatInterface = ({ 
  messages, 
  setMessages, 
  selectedModel, 
  tokenCount, 
  setTokenCount,
  leftSidebarOpen,
  rightSidebarOpen,
  toggleLeftSidebar,
  toggleRightSidebar
}) => {
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [abortController, setAbortController] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const [totalTokens, setTotalTokens] = useState({ input: 0, output: 0, total: 0 });
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [selectedImages, setSelectedImages] = useState([]);
  
  // Generate or get session ID
  const [sessionId] = useState(() => {
    let id = localStorage.getItem('chat_session_id');
    if (!id) {
      id = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('chat_session_id', id);
    }
    return id;
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Focus input after sending message
  const focusInput = () => {
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 100);
  };

  // Auto-resize textarea function
  const autoResizeTextarea = (textarea) => {
    if (!textarea) return;
    
    // Reset height to calculate new height
    textarea.style.height = 'auto';
    
    // Set new height based on scroll height
    const newHeight = Math.min(textarea.scrollHeight, 200); // Max 200px
    textarea.style.height = newHeight + 'px';
  };

  // Handle image file selection
  const handleImageSelect = (files) => {
    const imageFiles = Array.from(files).filter(file => 
      file.type.startsWith('image/') && file.size <= 10 * 1024 * 1024 // 10MB limit
    );
    
    imageFiles.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const imageData = {
          id: Date.now() + Math.random(),
          file: file,
          url: e.target.result,
          name: file.name
        };
        setSelectedImages(prev => [...prev, imageData]);
      };
      reader.readAsDataURL(file);
    });
  };

  // Handle file input change
  const handleFileChange = (e) => {
    if (e.target.files.length > 0) {
      handleImageSelect(e.target.files);
      e.target.value = ''; // Reset file input
    }
  };

  // Handle paste event for images
  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) {
          handleImageSelect([file]);
        }
        break;
      }
    }
  };

  // Remove selected image
  const removeImage = (imageId) => {
    setSelectedImages(prev => prev.filter(img => img.id !== imageId));
  };

  // Load session history on mount
  useEffect(() => {
    const loadSessionHistory = async () => {
      setIsLoadingHistory(true);
      console.log(`Loading session history for: ${sessionId} with model: ${selectedModel}`);
      
      try {
            const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
    const url = `${apiBase}/sessions/${sessionId}/history?model_id=${selectedModel}`;
        console.log(`Fetching from: ${url}`);
        
        const response = await fetch(url);
        console.log(`Response status: ${response.status}`);
        
        if (response.ok) {
          const data = await response.json();
          console.log('Session history response:', data);
          
          if (data.exists && data.messages && data.messages.length > 0) {
            console.log(`Setting ${data.messages.length} messages to UI`);
            setMessages(data.messages);
          } else {
            console.log('No messages found or session does not exist');
            if (data.exists === false) {
              console.log('Session does not exist on backend');
            } else if (!data.messages) {
              console.log('No messages property in response');
            } else if (data.messages.length === 0) {
              console.log('Messages array is empty');
            }
          }
        } else {
          console.error(`Failed to fetch session history: ${response.status} ${response.statusText}`);
        }
      } catch (error) {
        console.error('Error loading session history:', error);
      } finally {
        // Ensure loading is visible for at least 500ms
        setTimeout(() => {
          setIsLoadingHistory(false);
        }, 500);
      }
    };

    loadSessionHistory();
    focusInput();
  }, [sessionId, selectedModel, setMessages]);

  useEffect(() => {
    if (!isLoading) {
      focusInput();
    }
  }, [isLoading]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      // ESC key - focus input and clear if empty, or clear input if has content
      if (e.key === 'Escape') {
        e.preventDefault();
        if (inputRef.current) {
          if (inputMessage.trim()) {
            setInputMessage('');
            // Reset textarea height
            inputRef.current.style.height = 'auto';
          }
          inputRef.current.focus();
        }
      }
    };

    document.addEventListener('keydown', handleGlobalKeyDown);
    document.addEventListener('paste', handlePaste);
    
    return () => {
      document.removeEventListener('keydown', handleGlobalKeyDown);
      document.removeEventListener('paste', handlePaste);
    };
  }, [handlePaste, inputMessage]);

  // Auto-resize textarea on mount and when inputMessage changes
  useEffect(() => {
    if (inputRef.current) {
      autoResizeTextarea(inputRef.current);
    }
  }, [inputMessage]);

  const stopGeneration = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setIsLoading(false);
      
      // Mark last message as stopped
      setMessages(prev => prev.map((msg, index) => 
        index === prev.length - 1 && msg.isStreaming
          ? { ...msg, isStreaming: false, content: msg.content + ' [Stopped]' }
          : msg
      ));
      
      focusInput();
    }
  };

  const sendMessage = async () => {
    if ((!inputMessage.trim() && selectedImages.length === 0) || isLoading) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputMessage,
      images: selectedImages.map(img => ({
        url: img.url,
        name: img.name
      })),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setSelectedImages([]);
    
    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
    
    setIsLoading(true);

    // Create initial AI message for streaming
    const aiMessageId = Date.now() + 1;
    const aiMessage = {
      id: aiMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      model: selectedModel,
      isStreaming: true
    };

    setMessages(prev => [...prev, aiMessage]);

    // Create abort controller
    const controller = new AbortController();
    setAbortController(controller);

    try {
      const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
      // Use direct path for chat endpoint to leverage nginx SSE streaming config
      const chatBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '';
      
      // Prepare request body with images
      const requestBody = {
        message: inputMessage,
        model_id: selectedModel,
        session_id: sessionId
      };

      // Add images if any
      if (selectedImages.length > 0) {
        requestBody.images = selectedImages.map(img => ({
          data: img.url,
          name: img.name
        }));
      }

      const response = await fetch(`${chatBase}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedContent = '';
      let messageTokens = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              break;
            }

            try {
              const parsed = JSON.parse(data);
              
              if (parsed.type === 'content') {
                accumulatedContent += parsed.content;
                // Update UI immediately for each chunk, preserving formatting
                setMessages(prev => prev.map(msg => 
                  msg.id === aiMessageId 
                    ? { ...msg, content: accumulatedContent }
                    : msg
                ));
              } else if (parsed.type === 'tool_use') {
                // Show tool usage with input details
                const toolInfo = parsed.input ? ` (${JSON.stringify(parsed.input).slice(0, 50)}...)` : '';
                accumulatedContent += `\n`;
                setMessages(prev => prev.map(msg => 
                  msg.id === aiMessageId 
                    ? { ...msg, content: accumulatedContent + `\n\n🔧 Using tool: ${parsed.tool_name}${toolInfo}` }
                    : msg
                ));
              } else if (parsed.type === 'tool_result') {
                // Tool result received with details
                
                const resultInfo = parsed.result;
                console.log(`${resultInfo}`)
                accumulatedContent += `${resultInfo}\n\n`;
                setMessages(prev => prev.map(msg => 
                  msg.id === aiMessageId 
                    ? { ...msg, content: accumulatedContent }
                    : msg
                ));
              } else if (parsed.type === 'image') {
                // Handle image from event_loop_metrics
                setMessages(prev => prev.map(msg => 
                  msg.id === aiMessageId 
                    ? { 
                        ...msg, 
                        content: accumulatedContent + `\n\n![Generated Image](${parsed.url})`,
                        images: [...(msg.images || []), { url: parsed.url, filename: parsed.filename }]
                      }
                    : msg
                ));
              } else if (parsed.type === 'metrics') {
                // Handle metrics information
                console.log('Received metrics:', parsed.data);
              } else if (parsed.type === 'tokens') {
                messageTokens = parsed;
                setTotalTokens(prev => ({
                  input: prev.input + parsed.input,
                  output: prev.output + parsed.output,
                  total: prev.total + parsed.total
                }));
                setTokenCount(prev => prev + parsed.total);
              }
            } catch (e) {
              // Ignore JSON parse errors for partial chunks
            }
          }
        }
      }

      // Mark streaming as complete
      setMessages(prev => prev.map(msg => 
        msg.id === aiMessageId 
          ? { ...msg, isStreaming: false, tokens: messageTokens }
          : msg
      ));

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Request aborted');
        return;
      }
      
      console.error('Error sending message:', error);
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Error sending message: ${error.message}`,
        timestamp: new Date().toISOString(),
        model: selectedModel,
        isError: true
      };
      setMessages(prev => [...prev.slice(0, -1), errorMessage]);
    } finally {
      setIsLoading(false);
      setAbortController(null);
      focusInput();
    }
  };

  const handleKeyDown = (e) => {
    // Enter without Shift - send message (also check isComposing for IME input like Japanese/Korean)
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (!isLoading && inputMessage.trim()) {
        sendMessage();
      }
    }
    // Escape - clear input or focus
    else if (e.key === 'Escape') {
      e.preventDefault();
      if (inputMessage.trim()) {
        setInputMessage('');
        // Reset textarea height
        if (e.target) {
          e.target.style.height = 'auto';
        }
      }
      // Keep focus on input
      e.target.blur();
      setTimeout(() => e.target.focus(), 0);
    }
  };

  const clearMessages = async () => {
    // Clear current session on backend
    try {
      const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
      await fetch(`${apiBase}/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      console.log(`Cleared session ${sessionId} from backend`);
    } catch (error) {
      console.error('Error clearing session:', error);
    }
    
    // Clear UI
    setMessages([]);
    setTotalTokens({ input: 0, output: 0, total: 0 });
    setTokenCount(0);
    focusInput();
  };

  const newSession = async () => {
    // Clear current session on backend
    try {
      const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
      await fetch(`${apiBase}/sessions/${sessionId}`, {
        method: 'DELETE'
      });
    } catch (error) {
      console.error('Error clearing session:', error);
    }
    
    // Clear messages
    setMessages([]);
    setTotalTokens({ input: 0, output: 0, total: 0 });
    setTokenCount(0);
    
    // Generate new session ID
    const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem('chat_session_id', newId);
    
    // Force re-render with new session (would need to lift state up to parent)
    window.location.reload();
  };

  const formatModelName = (modelId) => {
    // Define custom names for specific models
    const modelNames = {
      'global.anthropic.claude-sonnet-4-5-20250929-v1:0': 'Claude Sonnet 4.5',
      'us.anthropic.claude-sonnet-4-20250514-v1:0': 'Claude Sonnet 4',
      'us.anthropic.claude-3-5-sonnet-20241022-v2:0': 'Claude 3.5 Sonnet',
      'us.amazon.nova-pro-v1:0': 'Nova Pro',
      'openai.gpt-oss-20b-1:0': 'GPT-OSS 20B',
      'openai.gpt-oss-120b-1:0': 'GPT-OSS 120B'
    };

    // Return custom name if available
    if (modelNames[modelId]) {
      return modelNames[modelId];
    }

    // Fallback to formatted version
    return modelId
      .replace('us.amazon.', '')
      .replace('us.anthropic.', '')
      .replace('anthropic.', '')
      .replace('-v1:0', '')
      .replace('-v2:0', '')
      .replace('-20250219', '')
      .replace('-20250514', '')
      .replace('-20241022', '')
      .replace('-20240307', '')
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <div className="chat-interface">
      {/* Chat Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          {!leftSidebarOpen && (
            <button 
              className="expand-sidebar-btn" 
              onClick={toggleLeftSidebar}
              title="Open configuration"
            >
              ⚙️
            </button>
          )}
          <div className="chat-info">
            <div className="chat-title">AI Assistant</div>
            <div className="chat-subtitle">
              {formatModelName(selectedModel)} • {messages.length} messages
            </div>
          </div>
        </div>
        
        <div className="chat-header-right">
          {totalTokens.total > 0 && (
            <div className="token-display">
              <div className="token-stats">
                <span className="token-stat">
                  <span className="token-label">IN</span>
                  <span className="token-value">{totalTokens.input}</span>
                </span>
                <span className="token-stat">
                  <span className="token-label">OUT</span>
                  <span className="token-value">{totalTokens.output}</span>
                </span>
              </div>
              <div className="total-tokens">{totalTokens.total} tokens</div>
            </div>
          )}
          
          <button 
            className="clear-chat-btn"
            onClick={clearMessages}
            title="Clear conversation"
          >
            🗑️
          </button>
          
          <button 
            className="new-session-btn"
            onClick={newSession}
            title="Start new session"
          >
            ➕
          </button>
          
          {!rightSidebarOpen && (
            <button 
              className="expand-sidebar-btn" 
              onClick={toggleRightSidebar}
              title="Open server logs"
            >
              📋
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="messages-container">
        {isLoadingHistory ? (
          <div className="loading-history">
                            <div className="loading-spinner"></div>
            <div>Loading conversation history...</div>
          </div>
        ) : messages.length === 0 ? (
          <div className="empty-chat">
            <div className="empty-icon">✨</div>
            <div className="empty-title">Ready to Boost Your Productivity?</div>
            <div className="empty-description">
              I'm your AI-powered productivity assistant! From calculating complex numbers to checking weather 
              and managing your schedule, I'm here to make your daily tasks effortless and efficient.
            </div>
            <div className="example-prompts">
              <button 
                className="example-prompt"
                onClick={() => {
                  const message = "Check today's weather in San Francisco and if it's sunny, schedule a 2-hour outdoor team lunch for tomorrow at 12 PM.";
                  setInputMessage(message);
                  focusInput();
                }}
              >
                🌤️ Smart Weather & Scheduling
              </button>
              <button 
                className="example-prompt"
                onClick={() => {
                  const message = "Calculate the compound interest: $10,000 invested at 5.5% annual rate for 3 years.";
                  setInputMessage(message);
                  focusInput();
                }}
              >
                🧮 Advanced Financial Calculations
              </button>
              <button 
                className="example-prompt"
                onClick={() => {
                  const message = "Schedule 3 workout sessions this week: Monday at 7 AM, Wednesday at 7 AM, and Friday at 7 AM, each for 1 hour.";
                  setInputMessage(message);
                  focusInput();
                }}
              >
                🏃‍♂️ Fitness & Wellness Planning
              </button>
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.role}`}>
                <div className="message-header">
                  <div className="message-role">
                    {message.role === 'user' ? '👤 You' : '🤖 Assistant'}
                  </div>
                  <div className="message-meta">
                    {message.model && (
                      <span className="message-model">{formatModelName(message.model)}</span>
                    )}
                    <span className="message-time">
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
                <div className={`message-content ${message.isError ? 'error' : ''}`}>
                  {/* Display images if present */}
                  {message.images && message.images.length > 0 && (
                    <div className="message-images">
                      {message.images.map((image, index) => (
                        <img 
                          key={index} 
                          src={image.url} 
                          alt={image.name || `Image ${index + 1}`}
                          className="message-image"
                        />
                      ))}
                    </div>
                  )}
                  
                  {message.role === 'assistant' ? (
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  ) : (
                    message.content
                  )}
                  {message.isStreaming && (
                    <span className="streaming-cursor">▋</span>
                  )}
                </div>
                {message.tokens && (
                  <div className="message-tokens">
                    <span className="token-info">
                      {message.tokens.input}→{message.tokens.output} ({message.tokens.total} tokens)
                    </span>
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="input-container">
        <div className="input-wrapper">
          {/* Image preview section - Top */}
          {selectedImages.length > 0 && (
            <div className="image-preview-container">
              {selectedImages.map((image) => (
                <div key={image.id} className="image-preview">
                  <img src={image.url} alt={image.name} />
                  <button
                    className="image-preview-remove"
                    onClick={() => removeImage(image.id)}
                    title="Remove image"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          
          {/* Input section - Bottom */}
          <div className="input-section">
            <div className="input-actions">
              <button
                className="attach-button"
                onClick={() => fileInputRef.current?.click()}
                title="Attach image"
              >
                📎
              </button>
            </div>
            
            <textarea
              ref={inputRef}
              value={inputMessage}
              onChange={(e) => {
                setInputMessage(e.target.value);
                autoResizeTextarea(e.target);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything! Calculate, plan, schedule, or just chat... ✨"
              className="message-input"
              rows={1}
              disabled={isLoading}
            />
            
            <button
              onClick={isLoading ? stopGeneration : sendMessage}
              disabled={!isLoading && !inputMessage.trim() && selectedImages.length === 0}
              className="send-button"
            >
              {isLoading ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M7 11L12 6L17 11M12 18V7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </button>
          </div>
        </div>
        
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileChange}
          className="file-input"
        />
      </div>
    </div>
  );
};

export default ChatInterface;