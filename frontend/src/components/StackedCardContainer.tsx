import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CardQuestion } from './CardQuestion';
import type { Message } from '../types';

interface StackedCardContainerProps {
  messages: Message[];
  isLoading: boolean;
  onSelect: (message: string) => void;
}

export const StackedCardContainer: React.FC<StackedCardContainerProps> = ({
  messages,
  isLoading,
  onSelect,
}) => {
  // Get the last 3 bot messages to create the stack effect
  const lastBotMessages = [...messages]
    .reverse()
    .filter(message => message.type === 'bot')
    .slice(0, 3);

  // Stack animation variants
  const stackVariants = {
    active: {
      scale: 1,
      y: 0,
      opacity: 1,
      zIndex: 30,
      transition: { duration: 0.5 }
    },
    behind1: {
      scale: 0.95,
      y: 20,
      opacity: 0.5,
      zIndex: 20,
      transition: { duration: 0.5 }
    },
    behind2: {
      scale: 0.9,
      y: 40,
      opacity: 0.2,
      zIndex: 10,
      transition: { duration: 0.5 }
    },
    exit: {
      scale: 1.05,
      y: -30,
      opacity: 0,
      zIndex: 40,
      transition: { duration: 0.4 }
    },
    enter: {
      scale: 0.9,
      y: 40,
      opacity: 0,
      zIndex: 10,
      transition: { duration: 0.3 }
    }
  };

  // Function to determine card position variant
  const getCardVariant = (index: number) => {
    switch (index) {
      case 0:
        return 'active';
      case 1:
        return 'behind1';
      case 2:
        return 'behind2';
      default:
        return 'behind2';
    }
  };

  return (
    <div className="relative h-[calc(100vh-120px)] flex items-center justify-center px-6">
      <div className="relative w-full max-w-lg mx-auto">
        <AnimatePresence mode="popLayout">
          {lastBotMessages.map((message, index) => (
            <motion.div
              key={message.timestamp.getTime()}
              className="absolute left-0 right-0 origin-center"
              initial="enter"
              animate={getCardVariant(index)}
              exit="exit"
              variants={stackVariants}
              style={{
                position: index === 0 ? 'relative' : 'absolute',
                top: 0,
                perspective: 1000
              }}
            >
              <div className={`w-full ${index === 0 ? '' : 'pointer-events-none'}`}>
                <CardQuestion
                  message={message}
                  isVisible={true}
                  onSelect={onSelect}
                  isLoading={isLoading && index === 0}
                />
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};
