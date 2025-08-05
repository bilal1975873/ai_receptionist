import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Message } from '../types';

interface CardQuestionProps {
  message: Message;
  isVisible: boolean;
  onSelect: (text: string) => void;
  isLoading: boolean;
}

interface Option {
  display: string;
  value: string;
}

export const CardQuestion: React.FC<CardQuestionProps> = ({
  message,
  isVisible,
  onSelect,
  isLoading,
}) => {
  const safeContent = typeof message.content === 'string' ? message.content : '';
  const lines = safeContent.split('\n');
  const options = lines.filter(line => line.match(/^\d+\./));
  const isEmployeeSelection = lines[0]?.toLowerCase().includes('found') && lines[0]?.toLowerCase().includes('match');
  // Show green button for any 'complete' step, including early arrival
  const isCompletionMessage = message.type === 'bot' && (
    safeContent.toLowerCase().includes('registration is complete') ||
    safeContent.toLowerCase().includes('registration successful') ||
    safeContent.toLowerCase().includes('start new registration') ||
    safeContent.toLowerCase().includes('please come back within 30 minutes before your scheduled time')
  );

  // Convert employee names into numbered options
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

  // --- Move isConfirmation before summaryInfo and prompt ---
  // Update: Always show Confirm/Edit buttons for admin support flow confirmation step, matching other flows
  const isAdminSupportConfirmation = message.type === 'bot' && (
    safeContent.toLowerCase().includes('admin support team') &&
    safeContent.toLowerCase().includes('your check-in has been recorded') &&
    safeContent.toLowerCase().includes('name:') &&
    safeContent.toLowerCase().includes('cnic:') &&
    safeContent.toLowerCase().includes('phone:') &&
    safeContent.toLowerCase().includes('host:') &&
    safeContent.toLowerCase().includes('service:')
  );

  const isConfirmation = message.type === 'bot' && (
    (safeContent.toLowerCase().includes('confirm') && safeContent.toLowerCase().includes('edit')) ||
    (safeContent.includes('[confirm]') && safeContent.includes('[edit]')) ||
    (safeContent.toLowerCase().includes('confirm') && (
      safeContent.toLowerCase().includes('final check') || 
      safeContent.toLowerCase().includes('please review')
    )) ||
    isAdminSupportConfirmation
  );

  // Extract summary info for confirmation cards
  const summaryInfo = isConfirmation ? lines.filter(line =>
    line.toLowerCase().includes('name:') ||
    line.toLowerCase().includes('cnic:') ||
    line.toLowerCase().includes('phone:') ||
    line.toLowerCase().includes('host:') ||
    line.toLowerCase().includes('purpose:') ||
    line.toLowerCase().includes('supplier:') ||
    line.toLowerCase().includes('email:') ||
    line.toLowerCase().includes('meeting:')
  ) : [];

  // Remove summary info lines from the prompt to avoid duplication
  const prompt = isEmployeeSelection
    ? lines[0]
    : lines.filter(line =>
        !line.match(/^[\d]+\./) &&
        !line.trim().startsWith('🧍') &&
        !line.trim().startsWith('📦') &&
        !line.trim().startsWith('📅') &&
        !(
          isConfirmation && (
            line.toLowerCase().includes('name:') ||
            line.toLowerCase().includes('cnic:') ||
            line.toLowerCase().includes('phone:') ||
            line.toLowerCase().includes('host:') ||
            line.toLowerCase().includes('purpose:') ||
            line.toLowerCase().includes('supplier:') ||
            line.toLowerCase().includes('email:') ||
            line.toLowerCase().includes('meeting:')
          )
        ) &&
        line.trim() !== ''
      ).join(' ');

  // Detect emoji-based options for visitor type selection
  const emojiOptions = lines.filter(line =>
    line.trim().startsWith('🧍') ||
    line.trim().startsWith('📦') ||
    line.trim().startsWith('📅')
  ).map(line => {
    if (line.includes('Guest')) return { display: line.trim(), value: 'guest' };
    if (line.includes('Vendor')) return { display: line.trim(), value: 'vendor' };
    if (line.includes('Meeting')) return { display: line.trim(), value: 'prescheduled' };
    return { display: line.trim(), value: line.trim() };
  });

  // Custom: If the prompt is the intro greeting, show the five visitor type buttons
  const isIntroGreeting = prompt.trim().replace(/[’']/g, "'").includes("Oh look, another human at the gates of innovation. I'm your AI receptionist, not a therapist, so let's keep this short. You are:");
  const visitorTypeButtons = isIntroGreeting
    ? [
        { display: '🧍 Guest – here to sip coffee and nod?', value: 'guest' },
        { display: '📦 Vendor – bless us with cardboard and chaos?', value: 'vendor' },
        { display: '📅 Meeting – how official of you.', value: 'prescheduled' },
        { display: '🧾 CV / Interview / Joiner – chasing dreams or HR already owns you?', value: 'cv drop / interview / new joiner' },
        { display: '🛠️ Admin Support – External maintenance personnel reporting in?', value: 'admin support' },
      ]
    : [];



  const cardVariants = {
    enter: {
      opacity: 0,
      y: 20,
      scale: 0.95,
    },
    center: {
      opacity: 1,
      y: 0,
      scale: 1,
    },
    exit: {
      opacity: 0,
      y: -20,
      scale: 0.95,
    },
  };

  // --- CV Drop / Interview / New Joiner buttons ---
  const cvPrompt = prompt.toLowerCase().includes('cv drop') && prompt.toLowerCase().includes('interview') && prompt.toLowerCase().includes('new joiner');
  const cvFlowButtons = cvPrompt
    ? [
        { display: '📄 CV Drop', value: 'cv drop' },
        { display: '🧑‍💼 Interview', value: 'interview' },
        { display: '👥 New Joiner', value: 'new joiner' },
      ]
    : [];

  // Hide the prompt if it's the CV flow selection
  const isCVFlowPrompt = cvPrompt;

  // --- Admin Support Service Selection buttons ---
  const adminSupportPrompt = prompt.toLowerCase().includes('admin support') && prompt.toLowerCase().includes('who are you here as');
  const adminSupportButtons = adminSupportPrompt
    ? [
        { display: '🔧 Plumber – here to check the pipes?', value: 'plumber' },
        { display: '💡 Electrician – got wires to fix?', value: 'electrician' },
        { display: '🛠️ Carpenter – on-site for repairs?', value: 'carpenter' },
        { display: '🎨 Painter – paintwork duty today?', value: 'painter' },
        { display: '📝 Other – something else?', value: 'other' },
      ]
    : [];

  // Hide the prompt if it's the Admin Support flow selection
  const isAdminSupportFlowPrompt = adminSupportPrompt;

  const showButtons = message.type === 'bot' && (options.length > 0 || emojiOptions.length > 0 || isConfirmation || isEmployeeSelection || isCompletionMessage || adminSupportButtons.length > 0);

  return (
    <AnimatePresence mode="wait">
      {isVisible && (
        <motion.div
          variants={cardVariants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="fixed inset-0 flex items-center justify-center p-2 sm:p-4 md:p-6"
        >
          <div
            className="w-full max-w-md sm:max-w-lg rounded-xl p-3 sm:p-5 md:p-6 pt-3 sm:pt-4 shadow-2xl border border-gray-700 backdrop-blur-md"
            style={{
              background: 'rgba(20, 24, 34, 0.78)', // dark, semi-transparent
              boxShadow: '0 8px 32px 0 rgba(239, 68, 68, 0.37)', // red shadow
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            {/* Question Content */}
            <div className="space-y-3 sm:space-y-4">
              {/* Main Prompt */}
              {!isCVFlowPrompt && !isAdminSupportFlowPrompt && (
                <h2 className="text-base sm:text-lg md:text-xl text-white font-medium">{prompt}</h2>
              )}

              {/* Summary Block for Confirmation */}
              {summaryInfo.length > 0 && (
                <div className="mb-2 text-sm text-gray-200 whitespace-pre-line border border-gray-700 rounded-lg p-3 bg-gray-900/70">
                  {summaryInfo.join('\n')}
                </div>
              )}              {/* Options */}
              {(showButtons || visitorTypeButtons.length > 0 || cvFlowButtons.length > 0 || adminSupportButtons.length > 0) && (
                <div className="grid gap-2 sm:gap-3 mt-3 sm:mt-4">
                  {/* Completion Message with New Registration Button */}
                  {isCompletionMessage && (
                    <button
                      onClick={() => onSelect('new')}
                      className="w-full px-4 py-3 text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors font-medium text-center"
                    >
                      Start New Registration
                    </button>
                  )}

                  {/* Visitor Type Buttons for Intro Greeting */}
                  {visitorTypeButtons.length > 0 && visitorTypeButtons.map(opt => (
                    <button
                      key={opt.value}
                      className="w-full px-3 sm:px-4 py-2 text-left text-white bg-gradient-to-r from-red-600 via-red-700 to-red-800 rounded-lg transition-colors font-medium text-sm sm:text-base"
                      onClick={() => onSelect(opt.value)}
                      disabled={isLoading}
                    >
                      {opt.display}
                    </button>
                  ))}

                  {/* Employee Selection Options */}
                  {isEmployeeSelection && (
                    <>
                      {employeeNames.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => onSelect(option.value)}
                          className="w-full px-3 sm:px-4 py-2 text-left text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors font-medium text-sm sm:text-base"
                        >
                          {option.display}
                        </button>
                      ))}
                      {nonEmployeeLines.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => onSelect(option.value)}
                          className="w-full px-3 sm:px-4 py-2 text-left text-white bg-gray-700 hover:bg-gray-800 rounded-lg transition-colors font-medium text-sm sm:text-base"
                        >
                          {option.display}
                        </button>
                      ))}
                    </>
                  )}

                  {/* Numbered Options */}
                  {!isEmployeeSelection && options.map((option) => {
                    const [num, ...textParts] = option.split('.');
                    return (
                      <button
                        key={num}
                        onClick={() => onSelect(num)}
                        className="w-full px-3 sm:px-4 py-2 text-left text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors font-medium text-sm sm:text-base"
                      >
                        {textParts.join('.').trim()}
                      </button>
                    );
                  })}

                  {/* Emoji-based Visitor Type Options */}
                  {emojiOptions.length > 0 && emojiOptions.map(opt => (
                    <button
                      key={opt.value}
                      className="w-full px-3 sm:px-4 py-2 text-left text-white bg-gradient-to-r from-red-600 via-red-700 to-red-800 rounded-lg transition-colors font-medium text-sm sm:text-base"
                      onClick={() => onSelect(opt.value)}
                      disabled={isLoading}
                    >
                      {opt.display}
                    </button>
                  ))}

                  {/* CV Drop / Interview / New Joiner buttons */}
                  {cvFlowButtons.length > 0 && (
                    <>
                      <div className="text-white mb-2 mt-2">Please select:</div>
                      {cvFlowButtons.map(btn => (
                        <button
                          key={btn.value}
                          className="w-full px-3 sm:px-4 py-2 text-left text-white bg-gradient-to-r from-red-600 via-red-700 to-red-800 rounded-lg transition-colors font-medium text-sm sm:text-base"
                          onClick={() => onSelect(btn.value)}
                          disabled={isLoading}
                        >
                          {btn.display}
                        </button>
                      ))}
                    </>
                  )}

                  {/* Admin Support Service Selection buttons */}
                  {adminSupportButtons.length > 0 && (
                    <>
                      <div className="text-white mb-2 mt-2">Please select:</div>
                      {adminSupportButtons.map(btn => (
                        <button
                          key={btn.value}
                          className="w-full px-3 sm:px-4 py-2 text-left text-white bg-gradient-to-r from-red-600 via-red-700 to-red-800 rounded-lg transition-colors font-medium text-sm sm:text-base"
                          onClick={() => onSelect(btn.value)}
                          disabled={isLoading}
                        >
                          {btn.display}
                        </button>
                      ))}
                    </>
                  )}

                  {/* Confirmation Buttons */}
                  {isConfirmation && (
                    <div className="flex gap-2 sm:gap-3">
                      <button
                        onClick={() => onSelect('confirm')}
                        className="flex-1 px-3 sm:px-4 py-2 text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm sm:text-base"
                        disabled={isLoading}
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => onSelect('edit')}
                        className="flex-1 px-3 sm:px-4 py-2 text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm sm:text-base"
                        disabled={isLoading}
                      >
                        Edit
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Loading Indicator */}
              {isLoading && (
                <div className="flex items-center justify-center space-x-2 text-red-500 opacity-75 mt-4">
                  <span className="text-base">Please wait</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 rounded-full bg-current animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-current animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 rounded-full bg-current animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
