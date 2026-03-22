import React, { useState, useEffect } from 'react';
import './LeftSidebar.css';

const LeftSidebar = ({ selectedModel, setSelectedModel, onClose }) => {
  const [models, setModels] = useState([]);
  const [mcpServers, setMcpServers] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchModels();
    fetchMcpServers();
  }, []);

  const fetchModels = async () => {
    try {
          const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
    const response = await fetch(`${apiBase}/models`);
      const data = await response.json();
      setModels(data);
    } catch (error) {
      console.error('Error fetching models:', error);
    }
  };

  const fetchMcpServers = async () => {
    try {
          const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
    const response = await fetch(`${apiBase}/mcp/servers`);
      const data = await response.json();
      const transformedData = Object.keys(data).reduce((acc, serverName) => {
        acc[serverName] = {
          ...data[serverName],
          enabled: data[serverName].enabled !== undefined ? data[serverName].enabled : false,
          status: data[serverName].enabled ? 'ready' : 'disabled'
        };
        return acc;
      }, {});
      setMcpServers(transformedData);
    } catch (error) {
      console.error('Error fetching MCP servers:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleServer = async (serverName, enabled) => {
    try {
          const apiBase = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '/proxy/8000';
    const response = await fetch(`${apiBase}/mcp/servers/${serverName}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !enabled })
      });

      if (response.ok) {
        setMcpServers(prev => ({
          ...prev,
          [serverName]: {
            ...prev[serverName],
            enabled: !enabled,
            status: !enabled ? 'ready' : 'disabled'
          }
        }));
      }
    } catch (error) {
      console.error('Error toggling server:', error);
    }
  };

  const formatModelName = (model) => {
    return model.name || model.id
      .replace('us.amazon.', '')
      .replace('anthropic.', '')
      .replace('-v1:0', '')
      .replace('-v2:0', '')
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <div className="left-sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title">Configuration</div>
      </div>

      <div className="sidebar-content">
        {/* AI Models Section */}
        <div className="section">
          <div className="section-header">
            <span className="section-icon">🤖</span>
            <span className="section-title">AI Models</span>
          </div>

          <div className="model-selector">
            <label className="input-label">Current Model</label>
            <select 
              value={selectedModel} 
              onChange={(e) => setSelectedModel(e.target.value)}
              className="model-dropdown"
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {formatModelName(model)}
                </option>
              ))}
            </select>
          </div>

          {selectedModel && (
            <div className="model-info">
              <div className="model-details">
                {(() => {
                  const model = models.find(m => m.id === selectedModel);
                  return model ? (
                    <>
                      <div className="model-name">{formatModelName(model)}</div>
                      <div className="model-description">{model.description}</div>
                    </>
                  ) : null;
                })()}
              </div>
            </div>
          )}
        </div>

        {/* MCP Servers Section */}
        <div className="section">
          <div className="section-header">
            <span className="section-icon">🔧</span>
            <span className="section-title">MCP Servers</span>
          </div>

          {loading ? (
            <div className="loading-state">Loading servers...</div>
          ) : (
            <div className="servers-list">
              {Object.entries(mcpServers).map(([serverName, server]) => (
                <div key={serverName} className="server-item">
                  <div className="server-info">
                    <div className="server-header">
                      <span className="server-name">{server.name}</span>
                      <span className={`server-status ${server.enabled ? 'enabled' : 'disabled'}`}>
                        {server.enabled ? '●' : '○'}
                      </span>
                    </div>
                    <div className="server-description">{server.description}</div>
                  </div>
                  
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={server.enabled}
                      onChange={() => toggleServer(serverName, server.enabled)}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LeftSidebar; 