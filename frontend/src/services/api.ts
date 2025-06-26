import axios, { AxiosError } from 'axios';
import type { Visitor, ApiResponse, VisitorInfo } from '../types';
import { checkAuthAndRedirect } from './auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Add request interceptor for auth checks
api.interceptors.request.use(
  async config => {
    // Skip auth check for auth-related endpoints
    if (!config.url?.includes('/auth/')) {
      const isAuth = await checkAuthAndRedirect();
      if (!isAuth) {
        return Promise.reject(new Error('Authentication required'));
      }
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  response => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      window.location.href = '/login';
      return Promise.reject(new Error('Authentication required'));
    }
    return Promise.reject(error);
  }
);

export const visitorService = {
  async createVisitor(visitor: Visitor): Promise<ApiResponse<Visitor>> {
    try {
      const response = await api.post<ApiResponse<Visitor>>('/visitors/', visitor);
      return response.data;
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'An error occurred while creating visitor',
      };
    }
  },

  async getVisitors(): Promise<ApiResponse<Visitor[]>> {
    try {
      const response = await api.get<ApiResponse<Visitor[]>>('/visitors/');
      return response.data;
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'An error occurred while fetching visitors',
      };
    }
  },

  async getVisitorByCNIC(cnic: string): Promise<ApiResponse<Visitor>> {
    try {
      const response = await api.get<ApiResponse<Visitor>>(`/visitors/${cnic}`);
      return response.data;
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'An error occurred while fetching visitor',
      };
    }
  },

  async updateVisitor(cnic: string, visitor: Partial<Visitor>): Promise<ApiResponse<Visitor>> {
    try {
      const response = await api.put<ApiResponse<Visitor>>(`/visitors/${cnic}`, visitor);
      return response.data;
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'An error occurred while updating visitor',
      };
    }
  },

  async deleteVisitor(cnic: string): Promise<ApiResponse<void>> {
    try {
      await api.delete(`/visitors/${cnic}`);
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'An error occurred while deleting visitor',
      };
    }
  },

  async processMessage(
    message: string,
    currentStep: string,
    visitorInfo: VisitorInfo
  ): Promise<{
    response: string;
    nextStep: string;
    visitorInfo: VisitorInfo;
  }> {
    // Remove undefined fields from visitorInfo
    const rawVisitorInfo = {
      ...visitorInfo,
      employee_selection_mode: visitorInfo.employee_selection_mode || false,
      employee_matches: visitorInfo.employee_matches || [],
      visitor_type: visitorInfo.type || visitorInfo.visitor_type,
      visitor_name: visitorInfo.full_name || visitorInfo.visitor_name,
      visitor_cnic: visitorInfo.cnic || visitorInfo.visitor_cnic,
      visitor_phone: visitorInfo.phone || visitorInfo.visitor_phone,
      visitor_email: visitorInfo.email,
      host_confirmed: visitorInfo.host,
      host_email: visitorInfo.host_email,
      host_requested: visitorInfo.host_requested,
      purpose: visitorInfo.purpose,
      scheduled_meeting: visitorInfo.scheduled_meeting,
    };
    const sanitizedVisitorInfo = Object.fromEntries(
      Object.entries(rawVisitorInfo).filter((entry) => entry[1] !== undefined)
    );
    try {
      const response = await api.post<{
        response: string;
        next_step: string;
        visitor_info: VisitorInfo;
      }>('/process-message/', {
        message,
        current_step: currentStep,
        visitor_info: sanitizedVisitorInfo,
      });

      const { response: botResponse, next_step, visitor_info } = response.data;
      
      if (!botResponse || typeof botResponse !== 'string') {
        throw new Error('Invalid response from server: Missing or invalid response message');
      }
      
      if (!next_step || typeof next_step !== 'string') {
        throw new Error('Invalid response from server: Missing or invalid next step');
      }
      
      if (!visitor_info || typeof visitor_info !== 'object') {
        throw new Error('Invalid response from server: Missing or invalid visitor info');
      }

      return {
        response: botResponse,
        nextStep: next_step,
        visitorInfo: visitor_info,
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 401) {
          throw new Error('Your session has expired. Please log in again.');
        } else if (error.response?.status === 429) {
          throw new Error('Too many requests. Please wait a moment and try again.');
        } else if (error.response?.data?.error) {
          throw new Error(`Server error: ${error.response.data.error}`);
        } else if (!error.response) {
          throw new Error('Network error: Could not connect to server');
        } else {
          throw new Error(`Server error: ${error.response.status} ${error.response.statusText}`);
        }
      }
      throw new Error(error instanceof Error ? error.message : 'An unexpected error occurred while processing your message');
    }
  },
};
