// Frontend - App.jsx
import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Zap, Calculator, Brain, Sparkles, AlertCircle, Wifi, WifiOff } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const App = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      content: "Hello! I'm an AI assistant powered by GPT-4o and Wolfram Alpha. I can help with calculations, scientific queries, unit conversions, and general conversation. What would you like to know?",
      timestamp: new Date(),
      usedWolfram: false
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [examples, setExamples] = useState({ wolfram_examples: [], general_examples: [] });
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    checkConnection();
    loadExamples();
  }, []);

  const checkConnection = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/`);
      if (response.ok) {
        const data = await response.json();
        setIsConnected(data.agent_initialized);
        setConnectionError(null);
      } else {
        setIsConnected(false);
        setConnectionError('Server responded with error');
      }
    } catch (error) {
      setIsConnected(false);
      setConnectionError('Cannot connect to server');
    }
  };

  const loadExamples = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/examples`);
      if (response.ok) {
        const data = await response.json();
        setExamples(data);
      }
    } catch (error) {
      console.error('Failed to load examples:', error);
    }
  };

  const callChatAPI = async (userMessage) => {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: userMessage,
        conversation_history: messages.map(msg => ({
          type: msg.type,
          content: msg.content,
          usedWolfram: msg.usedWolfram
        }))
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'API request failed');
    }

    return await response.json();
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: messages.length + 1,
      type: 'user',
      content: inputMessage,
      timestamp: new Date(),
      usedWolfram: false
    };

    setMessages(prev => [...prev, userMessage]);
    const currentMessage = inputMessage;
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await callChatAPI(currentMessage);
      
      const botMessage = {
        id: messages.length + 2,
        type: 'bot',
        content: response.content,
        timestamp: new Date(response.timestamp),
        usedWolfram: response.usedWolfram,
        processingTime: response.processingTime
      };

      setMessages(prev => [...prev, botMessage]);
      setConnectionError(null);
    } catch (error) {
      console.error('Chat API error:', error);
      const errorMessage = {
        id: messages.length + 2,
        type: 'bot',
        content: `I apologize, but I encountered an error: ${error.message}. Please make sure the backend server is running and try again.`,
        timestamp: new Date(),
        usedWolfram: false,
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
      setConnectionError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleExampleClick = (example) => {
    setInputMessage(example);
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <div className="bg-white shadow-lg border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-gradient-to-r from-green-500 to-blue-600 rounded-lg flex items-center justify-center">
                  <Brain className="w-5 h-5 text-white" />
                </div>
                <h1 className="text-2xl font-bold text-gray-800">AI Assistant</h1>
              </div>
              <div className="hidden md:flex items-center space-x-1 text-sm text-gray-600">
                <span>Powered by</span>
                <span className="font-semibold text-green-600">OpenAI</span>
                <span>&</span>
                <span className="font-semibold text-red-600">Wolfram Alpha</span>
              </div>
            </div>
            
            {/* Status and Logo Section */}
            <div className="flex items-center space-x-3">
                {/* Connection Status */}
                <div className={`hidden sm:flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${
                    isConnected 
                        ? 'bg-green-100 text-green-700' 
                        : 'bg-red-100 text-red-700'
                }`}>
                {isConnected ? (
                  <Wifi className="w-4 h-4" />
                ) : (
                  <WifiOff className="w-4 h-4" />
                )}
                <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
              </div>

              {/* OpenAI Logo */}
              <div className="hidden md:flex items-center space-x-2 bg-gray-100 px-3 py-1 rounded-full">
                <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
                <span className="text-sm font-medium text-gray-700">OpenAI</span>
              </div>
              
              {/* Wolfram Logo */}
              <div className="hidden md:flex items-center space-x-2 bg-gray-100 px-3 py-1 rounded-full">
                <div className="w-6 h-6 bg-red-500 rounded-full flex items-center justify-center">
                  <Calculator className="w-4 h-4 text-white" />
                </div>
                <span className="text-sm font-medium text-gray-700">Wolfram</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Connection Error Banner */}
      {connectionError && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-red-400 mr-2" />
            <div>
              <p className="text-sm text-red-700">
                Connection issue: {connectionError}
              </p>
              <p className="text-xs text-red-600 mt-1">
                Make sure the backend server is running on {API_BASE_URL}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-6">
          <div className="space-y-6">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`flex w-full max-w-4xl ${message.type === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                  {/* Avatar */}
                  <div className={`flex-shrink-0 ${message.type === 'user' ? 'ml-3' : 'mr-3'}`}>
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      message.type === 'user' 
                        ? 'bg-blue-500 text-white' 
                        : message.isError
                        ? 'bg-red-500 text-white'
                        : 'bg-gradient-to-r from-green-500 to-blue-600 text-white'
                    }`}>
                      {message.type === 'user' ? (
                        <User className="w-5 h-5" />
                      ) : (
                        <Bot className="w-5 h-5" />
                      )}
                    </div>
                  </div>

                  {/* Message Content */}
                  <div className={`flex flex-col ${message.type === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={`px-4 py-3 rounded-2xl max-w-2xl break-words ${
                      message.type === 'user'
                        ? 'bg-blue-500 text-white'
                        : message.isError
                        ? 'bg-red-50 text-red-800 border border-red-200'
                        : 'bg-white text-gray-800 shadow-lg border border-gray-200'
                    }`}>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                    </div>
                    
                    {/* Timestamp and Tool Usage */}
                    <div className="flex items-center space-x-2 mt-1 text-xs text-gray-500">
                      <span>{formatTime(message.timestamp)}</span>
                      {message.type === 'bot' && message.usedWolfram && (
                        <div className="flex items-center space-x-1 bg-red-100 text-red-600 px-2 py-1 rounded-full">
                          <Zap className="w-3 h-3" />
                          <span>Wolfram Alpha</span>
                        </div>
                      )}
                      {message.type === 'bot' && (
                        <span className="text-xs text-gray-400">
                            {message.usedWolfram ? '🧮 Computational' : '💭 Conversational'}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            
            {/* Loading Message */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="flex">
                  <div className="flex-shrink-0 mr-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-r from-green-500 to-blue-600 flex items-center justify-center text-white">
                      <Bot className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="bg-white rounded-2xl px-4 py-3 shadow-lg border border-gray-200">
                    <div className="flex items-center space-x-2">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      </div>
                      <span className="text-sm text-gray-600">Processing...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-white border-t border-gray-200 shadow-lg">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-end space-x-3">
            <div className="flex-1 relative">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything - from complex calculations to casual conversation..."
                className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows="1"
                style={{ minHeight: '48px', maxHeight: '120px' }}
                disabled={isLoading || !isConnected}
              />
            </div>
            <button
              onClick={handleSendMessage}
              disabled={isLoading || !inputMessage.trim() || !isConnected}
              className="bg-gradient-to-r from-green-500 to-blue-600 text-white p-3 rounded-xl hover:from-green-600 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          
          {/* Example Queries */}
          <div className="mt-3 space-y-2">
            {examples.wolfram_examples.length > 0 && (
              <div className="flex flex-wrap gap-2">
                <span className="text-xs text-gray-500 flex items-center">
                  <Calculator className="w-3 h-3 mr-1" />
                  Wolfram Alpha:
                </span>
                {examples.wolfram_examples.slice(0, 3).map((example, index) => (
                  <button
                    key={index}
                    onClick={() => handleExampleClick(example)}
                    className="text-xs bg-red-50 hover:bg-red-100 text-red-600 px-2 py-1 rounded-full transition-colors duration-200 border border-red-200"
                    disabled={isLoading || !isConnected}
                  >
                    {example}
                  </button>
                ))}
              </div>
            )}
            
            {examples.general_examples.length > 0 && (
              <div className="flex flex-wrap gap-2">
                <span className="text-xs text-gray-500 flex items-center">
                  <Sparkles className="w-3 h-3 mr-1" />
                  General:
                </span>
                {examples.general_examples.slice(0, 3).map((example, index) => (
                  <button
                    key={index}
                    onClick={() => handleExampleClick(example)}
                    className="text-xs bg-green-50 hover:bg-green-100 text-green-600 px-2 py-1 rounded-full transition-colors duration-200 border border-green-200"
                    disabled={isLoading || !isConnected}
                  >
                    {example}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;