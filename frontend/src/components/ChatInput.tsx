import React, { useState, useRef, useEffect } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  onStartOver?: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, isLoading, onStartOver }) => {
  const [message, setMessage] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [message]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSend(message.trim());
      setMessage('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form 
      onSubmit={handleSubmit}
      className="p-4 bg-gray-900/80 backdrop-blur-md border-t border-red-900/20 rounded-2xl"
    >
      <div className="flex items-center gap-3 max-w-4xl mx-auto">
        <textarea
          ref={inputRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Type your message..."
          className="flex-1 bg-gray-800/50 text-white rounded-xl px-4 py-3 resize-none max-h-16 outline-none focus:ring-2 focus:ring-red-500/50 transition-shadow scrollbar-hide border border-gray-700 focus:border-red-500"
          rows={1}
          disabled={isLoading}
          style={{ minHeight: 48, maxHeight: 64, overflow: 'hidden' }}
        />
        <button
          type="submit"
          disabled={!message.trim() || isLoading}
          className={`h-12 px-5 rounded-xl transition-all duration-200 font-semibold min-w-[100px] flex-shrink-0 ${
            message.trim() && !isLoading
              ? 'bg-gradient-to-r from-red-600 to-red-700 text-white hover:from-red-500 hover:to-red-600 transform hover:scale-105'
              : 'bg-gray-700 text-gray-400 cursor-not-allowed'
          }`}
        >
          Send
        </button>
        {onStartOver && (
          <button
            type="button"
            onClick={onStartOver}
            className="h-12 px-5 rounded-xl bg-gradient-to-r from-gray-600 to-gray-700 text-white hover:from-red-500 hover:to-red-600 transform hover:scale-105 min-w-[100px] transition-all duration-200 font-semibold flex-shrink-0"
            disabled={isLoading}
          >
            Start Over
          </button>
        )}
      </div>
    </form>
  );
};