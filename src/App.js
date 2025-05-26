// App.js
import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

import { BlockMath, InlineMath } from 'react-katex';
import 'katex/dist/katex.min.css';

import { parse } from 'mathjs';
import { Link } from 'react-router-dom';
// ...rest of your App.js


function App() {
  const [messages, setMessages] = useState([
    {
      sender: 'ai',
      mathSteps: [],
      explanation: 'Hello! I am your AI tutor. Ask me a math question!'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  // —————————————
  // Generic converter: turns any "/" into \frac{…}{…}
  // —————————————
  const expressionToLatex = (expr) => {
    try {
      const node = parse(expr);
      return node.toTex({
        parenthesis: 'keep',    // preserve existing parentheses
        implicit: 'show',       // show implied multiplications
        fraction: 'auto'        // convert a/b into \frac{a}{b}
      });
    } catch (err) {
      console.warn('mathjs parse error:', err);
      // fallback to raw expression
      return expr;
    }
  };

  // Renders explanation text with inline $…$ math
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
      const response = await axios.post('http://localhost:5000/api/chat', {
        message: input
      });

      const rawData = response.data;
      const parts = rawData.split('---');
      let mathSteps = [];
      let explanation = '';

      if (parts.length >= 2 && parts[0].toUpperCase().includes('MATH:')) {
        const mathPart = parts[0].replace(/^MATH:\s*/i, '');
        const lines = mathPart.split(/\r?\n/);
        mathSteps = lines
          .filter(line => /^\d+\.\s/.test(line))
          .map(line => line.replace(/^\d+\.\s*/, ''));
        explanation = parts[1].replace(/^EXPLANATION:\s*/i, '').trim();
      } else {
        explanation = rawData.trim();
      }

      const aiMessage = { sender: 'ai', mathSteps, explanation };
      setMessages(prev => [...prev, aiMessage]);
    } catch (err) {
      setMessages(prev => [...prev, {
        sender: 'ai',
        mathSteps: [],
        explanation: 'Error: Unable to connect to the server.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  // Grab last AI message
  const lastAIMessage = [...messages].reverse().find(m => m.sender === 'ai') || { mathSteps: [], explanation: '' };

  return (
    <div className="app">
      <div className="content-container">
        
        {/* Whiteboard area */}
        <div className="whiteboard math-block">
          <h3>Whiteboard</h3>
          {lastAIMessage.mathSteps.length > 0 ? (
            lastAIMessage.mathSteps.map((step, idx) => (
              <div key={idx} className="step">
                <span className="step-number">{idx + 1}.</span>
                <BlockMath>
                  {expressionToLatex(step)}
                </BlockMath>
              </div>
            ))
          ) : (
            <p>No math steps yet.</p>
          )}
        </div>

        {/* Explanation area */}
        <div className="explanation">
          {renderExplanationWithMath(lastAIMessage.explanation)}
        </div>
      </div>

      {/* Input section */}
      <div className="input-container">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Ask me a math question..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading}>Send</button>
      </div>

      {loading && <div className="loading-indicator">Thinking...</div>}
    </div>
  );
}

export default App;
