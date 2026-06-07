import React, { useState, useRef, useEffect, useContext } from 'react';
import { MessageSquare, X, Send, Bot, User, Loader, ChevronDown } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';
import './ChatbotWidget.css'; 

const ChatbotWidget = () => {
  const { user, token } = useContext(AuthContext);
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { id: 1, type: 'bot', text: 'Merhaba! Ben sizin kişisel portföy asistanınızım. Portföyünüz veya piyasalar hakkında bana sorular sorabilirsiniz.' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  if (!user) return null; // Sadece giriş yapmış kullanıcılar görebilir

  const toggleChat = () => setIsOpen(!isOpen);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const newMsgText = inputValue.trim();
    const newUserMsg = { id: Date.now(), type: 'user', text: newMsgText };
    setMessages(prev => [...prev, newUserMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/chatbot/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ message: newMsgText })
      });
      
      const data = await res.json();
      
      if (res.ok) {
        setMessages(prev => [...prev, { id: Date.now() + 1, type: 'bot', text: data.reply }]);
      } else {
        setMessages(prev => [...prev, { id: Date.now() + 1, type: 'bot', text: "Üzgünüm, bir bağlantı hatası oluştu. (Hata: " + (data.detail || "Bilinmiyor") + ")" }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { id: Date.now() + 1, type: 'bot', text: "Sunucuya bağlanılamadı. Lütfen internet bağlantınızı kontrol edin." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chatbot-container">
      {/* Floating Button */}
      <div className={`chatbot-toggle-wrapper ${isOpen ? 'hidden' : 'visible'}`}>
        <span className="chatbot-tooltip">Portföy Asistanı</span>
        <button 
          className="chatbot-toggle-btn glow-effect premium-border"
          onClick={toggleChat}
          title="Yapay Zeka Asistanı"
        >
          <MessageSquare size={24} color="#60a5fa" />
        </button>
      </div>

      {/* Chat Window */}
      <div className={`chatbot-window glass-panel premium-border ${isOpen ? 'open' : 'closed'}`}>
        {/* Header */}
        <div className="chatbot-header">
          <div className="chatbot-header-info">
            <Bot size={24} color="#60a5fa" className="drop-shadow-blue" />
            <div className="chatbot-titles">
              <h4>Portföy Asistanı</h4>
              <span className="chatbot-status">Yapay Zeka (Gemini RAG) ile Canlı</span>
            </div>
          </div>
          <button className="chatbot-close-btn" onClick={toggleChat}>
            <ChevronDown size={20} color="#94a3b8" />
          </button>
        </div>

        {/* Messages */}
        <div className="chatbot-messages">
          {messages.map((msg) => (
            <div key={msg.id} className={`chat-message ${msg.type}`}>
              <div className="message-icon">
                {msg.type === 'bot' ? <Bot size={16} color="#60a5fa" /> : <User size={16} color="#4ade80" />}
              </div>
              <div className="message-bubble">
                <p>{msg.text}</p>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="chat-message bot loading-message">
              <div className="message-icon"><Bot size={16} color="#60a5fa" /></div>
              <div className="message-bubble">
                <Loader size={16} color="#60a5fa" className="spin" /> <span style={{marginLeft: '0.5rem'}}>Asistan düşünüyor...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <form className="chatbot-input-area" onSubmit={handleSendMessage}>
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Portföyünüzü veya piyasayı sorun..."
            disabled={isLoading}
          />
          <button type="submit" disabled={!inputValue.trim() || isLoading} className="chatbot-send-btn glow-effect">
            <Send size={18} color="#fff" />
          </button>
        </form>
        
        {/* Disclaimer */}
        <div className="chatbot-disclaimer">
          ⚠️ Bu asistanın verdiği yanıtlar yapay zeka tarafından üretilmektedir ve <strong>kesinlikle yatırım tavsiyesi (YTD) değildir.</strong>
        </div>
      </div>
    </div>
  );
};

export default ChatbotWidget;
