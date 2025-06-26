export interface Visitor {
  type: 'guest' | 'vendor';
  full_name: string;
  cnic: string | null;
  phone: string;
  email?: string;
  host: string;
  host_email?: string;
  purpose: string;
  entry_time: string;
  exit_time?: string;
  is_group_visit: boolean;
  group_id?: string;
  total_members: number;
  group_members: GroupMember[];
}

export interface EmployeeMatch {
  displayName: string;
  email: string;
  department: string;
  jobTitle: string;
  id: string;
}

export interface ScheduledMeeting {
  start_time: string;
  subject: string;
}

export interface VisitorInfo extends Partial<Visitor> {
  visitor_type?: 'guest' | 'vendor' | 'prescheduled';
  visitor_name?: string;
  visitor_cnic?: string;
  visitor_phone?: string;
  visitor_email?: string;
  host_requested?: string;
  host_confirmed?: string;
  host_email?: string;
  scheduled_meeting?: ScheduledMeeting;
  verification_status?: string;
  supplier?: string;
  employee_selection_mode?: boolean;
  employee_matches?: EmployeeMatch[];
  registration_completed?: boolean;
}

export interface GroupMember {
  name: string;
  cnic: string;
  phone: string;
}

export interface Message {
  type: 'user' | 'bot';
  content: string;
  timestamp: Date;
}

export interface ChatState {
  messages: Message[];
  currentStep: string;
  visitorInfo: VisitorInfo;
  isLoading: boolean;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: {
    name?: string;
    email?: string;
    accessToken?: string;
  } | null;
  loading: boolean;
  error: string | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export type Timeout = ReturnType<typeof setTimeout>;
