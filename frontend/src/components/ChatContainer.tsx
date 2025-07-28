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
    <div className="relative min-h-[60vh] h-[calc(100dvh-120px)] w-full max-w-4xl mx-auto px-2 sm:px-4 md:px-6 pb-40 sm:pb-28 md:pb-20 flex flex-col justify-end">
      {lastBotMessage && (
        <CardQuestion
          message={lastBotMessage}
          isVisible={true}
          onSelect={onSend}
          isLoading={isLoading}
          //onStartOver={onStartOver}
        />
      )}
      {/* Responsive input at bottom */}
      <div className="fixed bottom-0 left-0 w-full flex justify-center z-20 px-1 sm:px-4 pb-2 sm:pb-6 pointer-events-none">
        <div className="w-full max-w-lg pointer-events-auto">
          <div className="bg-gray-900/90 backdrop-blur-sm rounded-xl border border-gray-700 shadow-lg">
            <ChatInput onSend={onSend} isLoading={isLoading} onStartOver={onStartOver} />
          </div>
        </div>
      </div>
    </div>
  );
};
