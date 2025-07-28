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
      className="p-2 sm:p-4 bg-gray-900/80 backdrop-blur-md border-t border-red-900/20 rounded-2xl"
    >
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3 max-w-4xl mx-auto">
        <textarea
          ref={inputRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Type your message..."
          className="flex-1 bg-gray-800/50 text-white rounded-xl px-3 py-2 sm:px-4 sm:py-3 resize-none max-h-16 outline-none focus:ring-2 focus:ring-red-500/50 transition-shadow scrollbar-hide border border-gray-700 focus:border-red-500 text-sm sm:text-base"
          rows={1}
          disabled={isLoading}
          style={{ minHeight: 36, maxHeight: 56, overflow: 'hidden' }}
        />
        <div className="flex gap-1 sm:gap-3 w-full sm:w-auto">
          <button
            type="submit"
            disabled={!message.trim() || isLoading}
            className={`h-10 sm:h-12 px-3 sm:px-5 rounded-xl transition-all duration-200 font-semibold min-w-[80px] sm:min-w-[100px] flex-1 sm:flex-initial text-sm sm:text-base ${
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
              className="h-10 sm:h-12 px-3 sm:px-5 rounded-xl bg-gradient-to-r from-gray-600 to-gray-700 text-white hover:from-red-500 hover:to-red-600 transform hover:scale-105 min-w-[80px] sm:min-w-[100px] transition-all duration-200 font-semibold flex-1 sm:flex-initial text-sm sm:text-base"
              disabled={isLoading}
            >
              Start Over
            </button>
          )}
        </div>
      </div>
    </form>
  );
};