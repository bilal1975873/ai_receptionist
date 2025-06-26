// Utility to determine if the input field should be shown for a given message
import type { Message } from '../types';

export function shouldShowInputField(message: Message): boolean {
  if (!message || message.type !== 'bot') return false;
  const safeContent = typeof message.content === 'string' ? message.content : '';
  const lines = safeContent.split('\n');
  const options = lines.filter(line => line.match(/^\d+\./));
  const isEmployeeSelection = lines[0]?.toLowerCase().includes('found') && lines[0]?.toLowerCase().includes('match');
  const prompt = isEmployeeSelection ?
    lines[0] :
    lines.filter(line => !line.match(/^\d+\./) && line.trim() !== '').join(' ');
  const isConfirmation = (
    (prompt.toLowerCase().includes('confirm') && prompt.toLowerCase().includes('edit')) ||
    (prompt.includes('[confirm]') && prompt.includes('[edit]')) ||
    (prompt.toLowerCase().includes('confirm') && (
      prompt.toLowerCase().includes('final check') || 
      prompt.toLowerCase().includes('please review')
    ))
  );
  const isCompletionMessage = safeContent.toLowerCase().includes('registration is complete');
  return (
    safeContent.toLowerCase().includes('cnic') ||
    safeContent.toLowerCase().includes('phone') ||
    safeContent.toLowerCase().includes('mobile number') ||
    safeContent.toLowerCase().includes('mobile no') ||
    safeContent.toLowerCase().includes('phone number') ||
    safeContent.toLowerCase().includes('phone no') ||
    safeContent.toLowerCase().includes('mobile') ||
    safeContent.toLowerCase().includes('name') ||
    safeContent.toLowerCase().includes('host') ||
    safeContent.toLowerCase().includes('host name') ||
    safeContent.toLowerCase().includes('purpose') ||
    (safeContent.toLowerCase().includes('enter') && !safeContent.toLowerCase().includes('none of these'))
  ) && !options.length && !isEmployeeSelection && !isConfirmation && !isCompletionMessage;
}
