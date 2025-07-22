import React from 'react';
import { ChatInput } from './ChatInput';
import { CardQuestion } from './CardQuestion';
import type { Message } from '../types';

interface ChatContainerProps {
  messages: Message[];
  isLoading: boolean;
  onSend: (message: string) => void;
}

export const ChatContainer: React.FC<ChatContainerProps & { onStartOver?: () => void }> = ({
  messages,
  isLoading,
  onSend,
  onStartOver,
}) => {
  // Get the last bot message to display
  const lastBotMessage = [...messages]
    .reverse()
    .find(message => message.type === 'bot');

  return (
    <div className="relative h-screen w-full max-w-4xl mx-auto px-6">
      {lastBotMessage && (
        <CardQuestion
          message={lastBotMessage}
          isVisible={true}
          onSelect={onSend}
          isLoading={isLoading}
          //onStartOver={onStartOver}
        />
      )}
      {/* Fixed input at bottom */}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 w-full max-w-lg mx-auto px-6">
        <div className="bg-gray-900/90 backdrop-blur-sm rounded-xl border border-gray-700 shadow-lg">
          <ChatInput onSend={onSend} isLoading={isLoading} onStartOver={onStartOver} />
        </div>
      </div>
    </div>
  );
};
