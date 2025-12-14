import type { ParsedResumeData } from '@/types';
import { getApiUrl,getApiUrl2, API_CONFIG, PARSER_URL } from '@/config/api';

/**
 * Uploads a resume file to the backend
 * @param file - The resume file to upload
 * @returns Promise with parsed resume data
 */
export async function uploadResume(file: File): Promise<ParsedResumeData> {
  const form = new FormData();
  form.append('file', file);
  form.append('file_type', 'resume');

  const res = await fetch(getApiUrl(API_CONFIG.ENDPOINTS.UPLOAD_RESUME), {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    // Try to get error details from response
    let errorMessage = 'Upload failed';
    try {
      const errorData = await res.json();
      errorMessage = errorData.message || errorData.detail || errorMessage;
    } catch {
      // If response is not JSON, use status text
      errorMessage = res.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return res.json();
}

/**
 * Ask a parser service to parse an uploaded resume by id.
 * @param id - the resume id returned from the upload endpoint
 * @param parserUrl - full URL of the parser API that accepts { resumeId, fileUrl }
 * @param fileUrl - optional absolute URL to the uploaded file so parser can fetch it directly
 */
export async function parseResume(id: string, parserUrl?: string, fileUrl?: string): Promise<ParsedResumeData> {
  // If caller doesn't specify a parserUrl, use the configured endpoint on our backend
  // Priority: explicit parserUrl passed to the helper -> PARSER_URL env var -> configured backend parse endpoint
  const url = getApiUrl2(API_CONFIG.ENDPOINTS.PARSE_RESUME);

  const body: any = { id: id };
  if (fileUrl) body.pdf_url = fileUrl;
  console.log("Parsing resume with body:", body);
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errorMessage = 'Parse request failed';
    try {
      const errorData = await res.json();
      errorMessage = errorData.message || errorData.detail || errorMessage;
    } catch {
      errorMessage = res.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  return res.json();
}

