import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { socAPI } from '../api/axiosInstance';
import { PiBrainBold, PiUserBold, PiPaperPlaneRightBold, PiTrashBold } from "react-icons/pi";
import './Chatting.css';

const initialMessage = { sender: 'bot', text: '안녕하세요. SOC Copilot입니다. 자연어로 위협 상황을 질문해 주세요.' };

const Chatting = () => {
  const [messages, setMessages] = useState([initialMessage]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const fetchChatHistory = async () => {
      try {
        const response = await socAPI.getChatHistory();
        const history = (response.data || []).map((item) => ({
          sender: item.sender,
          text: item.message,
        }));

        if (history.length > 0) {
          setMessages(history);
        }
      } catch (error) {
        console.error('채팅 기록을 불러오지 못했습니다:', error);
      }
    };

    void fetchChatHistory();
  }, []);

  const sendMessage = async () => {
    if (!input.trim()) return;
    
    const userMsg = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      // 챗봇 API 연동 (POST /api/v1/copilot/chat) 
      const response = await socAPI.postChat(userMsg.text);
      setMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: response.data.reply,
          actionResult: response.data.action_result || null,
        },
      ]);
    } catch {
      setMessages(prev => [...prev, { sender: 'bot', text: '서버 통신 오류가 발생했습니다.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const clearHistory = async () => {
    try {
      await socAPI.deleteChatHistory();
      setMessages([initialMessage]);
    } catch (error) {
      console.error('채팅 기록을 삭제하지 못했습니다:', error);
    }
  };

  return (
    <div className="chatting-container">
      <header className="page-header">
        <div>
          <h1>AI 보안 어시스턴트 코파일럿</h1>
          <p>GenAI 기반으로 위협 분석 및 대응을 도와주는 챗봇입니다.</p>
        </div>
        <button type="button" className="clear-chat-btn" onClick={clearHistory}>
          <PiTrashBold size={16} /> 대화 초기화
        </button>
      </header>
      
      <div className="chat-window">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-line ${msg.sender}`}>
            <div className="avatar">
              {msg.sender === 'bot' ? <PiBrainBold size={20}/> : <PiUserBold size={20}/>}
            </div>
            <div className="chat-bubble">
              {msg.sender === 'bot' ? <ReactMarkdown>{msg.text}</ReactMarkdown> : msg.text}
            </div>
          </div>
        ))}
        {isTyping && (
          <div className="chat-line bot">
            <div className="avatar"><PiBrainBold size={20}/></div>
            <div className="chat-bubble typing">분석 중<span className="typing-dots"><span>.</span><span>.</span><span>.</span></span></div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="이전 사건 분석, 혹은 조치 방법을 물어보세요..."
        />
        <button onClick={sendMessage}><PiPaperPlaneRightBold size={18}/></button>
      </div>
    </div>
  );
};

export default Chatting;
