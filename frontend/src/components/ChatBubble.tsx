import React from 'react';
import type { Message } from '../types';

interface ChatBubbleProps {
  message: Message;
  className?: string;
  onSelect?: (text: string) => void;
}

interface Option {
  display: string;
  value: string;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({ message, className = '', onSelect }) => {
  const isBot = message.type === 'bot';
  // Ensure message.content is always a string
  const safeContent = typeof message.content === 'string' ? message.content : '';
  // Extract numbered options and main prompt
  const lines = safeContent.split('\n');
  const options = lines.filter(line => line.match(/^\d+\./));
  
  // Handle employee selection differently
  const isEmployeeSelection = lines[0]?.toLowerCase().includes('found') && lines[0]?.toLowerCase().includes('match');
  
  // Check if this is a completion message
  const isCompletionMessage = isBot && (
    safeContent.toLowerCase().includes('registration is complete') ||
    (
      safeContent.toLowerCase().includes('registration successful') &&
      safeContent.toLowerCase().includes('rebel presence incoming')
    )
  );
  
  // Convert employee names into numbered options internally
  let counter = 1;
  const employeeNames: Option[] = isEmployeeSelection ? 
    lines.filter(line => 
      !line.toLowerCase().includes('found') && 
      !line.toLowerCase().includes('none of these') && 
      line.trim()
    ).map(name => ({
      display: name.trim(),
      value: String(counter++)
    }))
    : [];
  
  const nonEmployeeLines: Option[] = isEmployeeSelection ? 
    [{
      display: "None of these / Enter a different name",
      value: "0"
    }]
    : [];
  
  // Always use the first non-empty, non-numbered line as the main prompt (AI response)
  const prompt = lines.find(line => line.trim() && !line.match(/^\d+\./)) || safeContent;
  
  // Check if this is a confirmation message
  const isConfirmation = isBot && (
    // Check for messages containing both confirm and edit
    (prompt.toLowerCase().includes('confirm') && prompt.toLowerCase().includes('edit')) ||
    // Legacy format with [confirm] [edit]
    (prompt.includes('[confirm]') && prompt.includes('[edit]')) ||
    // Additional check for final check/review prompts
    (prompt.toLowerCase().includes('confirm') && (
      prompt.toLowerCase().includes('final check') || 
      prompt.toLowerCase().includes('please review')
    ))
  );
  // Try to extract summary/info if present (lines before the prompt)
  let summaryBlock = null;
  if (isConfirmation && lines.length > 1) {
    // If the first line(s) look like info, show them above the buttons
    const infoLines = lines.filter(line =>
      line.toLowerCase().includes('name:') ||
      line.toLowerCase().includes('cnic:') ||
      line.toLowerCase().includes('phone:') ||
      line.toLowerCase().includes('host:') ||
      line.toLowerCase().includes('purpose:')
    );
    if (infoLines.length > 0) {
      summaryBlock = (
        <div className="mb-2 text-sm text-gray-200 whitespace-pre-line border border-gray-700 rounded-lg p-3 bg-gray-900/70">
          {infoLines.join('\n')}
        </div>
      );
    }
  }
  const showButtons = isBot && (options.length > 0 || isConfirmation || isEmployeeSelection || isCompletionMessage);

  // If this is the initial visitor type selection, auto-send the correct number for each button
  const isVisitorTypePrompt = isBot && (
    prompt.toLowerCase().includes('please select your visitor type') ||
    prompt.toLowerCase().includes('select your visitor type')
  );

  // Map display text to backend value for visitor type
  const visitorTypeMap: Record<string, string> = {
    'i am here as a guest': '1',
    'i am a vendor': '2',
    'i have a pre-scheduled meeting': '3',
  };

  return (
    <div className={`flex ${isBot ? 'justify-start' : 'justify-end'} ${className}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isBot
            ? 'bg-gradient-to-br from-gray-800 to-gray-900 text-white mr-auto chat-shadow'
            : 'bg-gradient-to-br from-red-600 to-red-700 text-white ml-auto glow-effect'
        }`}
      >
        {showButtons ? (
          <>
            {summaryBlock}
            <div className="font-semibold text-base md:text-lg mb-2">{prompt}</div>
            <div className="flex flex-col gap-3 mt-2">
              {isConfirmation ? (
                <div className="flex gap-3">
                  <button
                    onClick={() => onSelect?.('confirm')}
                    className="flex-1 px-5 py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium text-base shadow-lg hover:shadow-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-green-400"
                  >
                    Confirm
                  </button>
                  <button
                    onClick={() => onSelect?.('edit')}
                    className="flex-1 px-5 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-medium text-base shadow-lg hover:shadow-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-red-400"
                  >
                    Edit
                  </button>
                </div>
              ) : isEmployeeSelection ? (
                <>
                  {employeeNames.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => onSelect?.(option.value)}
                      className="w-full text-left px-5 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-medium text-base shadow-lg hover:shadow-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-red-400"
                    >
                      {option.display}
                    </button>
                  ))}
                  {nonEmployeeLines.map((option) => (
                    <button
                      key={option.value}
                      onClick={() => onSelect?.(option.value)}
                      className="w-full text-left px-5 py-3 bg-gray-600 hover:bg-gray-700 text-white rounded-xl font-medium text-base shadow-lg hover:shadow-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-gray-400"
                    >
                      {option.display}
                    </button>
                  ))}
                </>
              ) : isCompletionMessage ? (
                <button
                  onClick={() => onSelect?.('ok')}
                  className="w-full text-left px-5 py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium text-base shadow-lg hover:shadow-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-green-400"
                >
                  Start New Registration
                </button>
              ) : (
                options.map((option, index) => {
                  const match = option.match(/^(\d+)\.\s*(.*)$/);
                  let valueToSend = option;
                  if (match) {
                    // If this is the supplier selection step, send the supplier name
                    const [, num, supplierName] = match;
                    // Check if the prompt is for supplier selection
                    if (prompt.toLowerCase().includes('select your supplier')) {
                      valueToSend = supplierName.trim();
                    } else {
                      valueToSend = num;
                    }
                  }
                  // If visitor type selection, map button text to backend value
                  const lower = option.toLowerCase().replace(/^\d+\.\s*/, '').trim();
                  const mappedValue = isVisitorTypePrompt && visitorTypeMap[lower] ? visitorTypeMap[lower] : valueToSend;
                  return (
                    <button
                      key={index}
                      onClick={() => onSelect?.(mappedValue)}
                      className="w-full text-left px-5 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-medium text-base shadow-lg hover:shadow-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-red-400"
                    >
                      {option.replace(/^\d+\.\s*/, '')}
                    </button>
                  );
                })
              )}
            </div>
          </>
        ) : (
          <p className="text-sm md:text-base whitespace-pre-wrap">{safeContent}</p>
        )}
        <span className="text-xs opacity-50 mt-3 block text-right">
          {message.timestamp.toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
};
