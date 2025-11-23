// API Configuration
// Update these URLs to match your backend endpoints

export const API_CONFIG = {
  // Base URL for your backend API
  // File service runs on port 8005
  // For production: your production API URL
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8005',
  
  // API Endpoints
  ENDPOINTS: {
    UPLOAD_RESUME: '/upload-file',
    START_INTERVIEW: '/api/start-interview',
    SUBMIT_ANSWER: '/api/submit-answer',
  },
} as const;

// Helper function to get full API URL
export function getApiUrl(endpoint: string): string {
  return `${API_CONFIG.BASE_URL}${endpoint}`;
}

