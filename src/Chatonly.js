// ChatOnly.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

import { InlineMath } from 'react-katex';
import 'katex/dist/katex.min.css';

function ChatOnly() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const renderExplanationWithMath = (text) => {
    const parts = text.split(/(\$[^$]+\$)/g);
    return parts.map((part, i) => {
      if (part.startsWith('$') && part.endsWith('$')) {
        return <InlineMath key={i}>{part.slice(1, -1)}</InlineMath>;
      }
      return <span key={i}>{part}</span>;
    });
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:5000/api/chat-basic', {
        message: input
      });

      const aiText = response.data;
      const aiMessage = { sender: 'ai', text: aiText };
      setMessages(prev => [...prev, aiMessage]);
    } catch (err) {
      setMessages(prev => [...prev, {
        sender: 'ai',
        text: 'Error: Unable to connect to the server.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  return (
    <div className="app">
      <div className="content-container">
        <div className="explanation">
          {messages.map((msg, idx) => (
            <div key={idx} className={msg.sender === 'user' ? 'user-msg' : 'ai-msg'}>
              {renderExplanationWithMath(msg.text)}
            </div>
          ))}
        </div>
      </div>

      <div className="input-container">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Ask me anything..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading}>Send</button>
      </div>

      {loading && <div className="loading-indicator">Thinking...</div>}
    </div>
  );
}

export default ChatOnly;
