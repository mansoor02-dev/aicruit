// API Configuration
// Update these URLs to match your backend endpoints

export const API_CONFIG = {
  // Base URL for your backend API
  // For development: 'http://localhost:8000' or your backend URL
  // For production: your production API URL
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8005',
  BASE_URL_2: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8006',
  
  // API Endpoints
  ENDPOINTS: {
    UPLOAD_RESUME: '/upload-file',
    PARSE_RESUME: '/parse-resume',
    START_INTERVIEW: '/start-interview',
    SUBMIT_ANSWER: '/submit-answer',
  },
} as const;

// Helper function to get full API URL
export function getApiUrl(endpoint: string): string {
  return `${API_CONFIG.BASE_URL}${endpoint}`;
}

export function getApiUrl2(endpoint: string): string {
  return `${API_CONFIG.BASE_URL_2}${endpoint}`;
}
// Optional parser URL can be set via NEXT_PUBLIC_PARSER_URL for external parser services
export const PARSER_URL = process.env.NEXT_PUBLIC_PARSER_URL || '';

