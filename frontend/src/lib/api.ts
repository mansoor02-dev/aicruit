const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
}

export class ApiError extends Error {
  public body?: any;
  constructor(message: string, public status?: number, body?: any) {
    super(message);
    this.name = 'ApiError';
    this.body = body;
  }
}

export const getAuthToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  const tokens = localStorage.getItem('aicruit_tokens');
  if (!tokens) return null;
  try {
    const parsed = JSON.parse(tokens);
    return parsed.access_token;
  } catch {
    return null;
  }
};

export const apiRequest = async <T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> => {
  const token = getAuthToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(errorData.detail || `HTTP ${response.status}`, response.status, errorData);
  }

  return response.json();
};

export const api = {
  get: <T = any>(endpoint: string) => apiRequest<T>(endpoint, { method: 'GET' }),
  post: <T = any>(endpoint: string, data?: any) => apiRequest<T>(endpoint, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  }),
  put: <T = any>(endpoint: string, data?: any) => apiRequest<T>(endpoint, {
    method: 'PUT',
    body: data ? JSON.stringify(data) : undefined,
  }),
  delete: <T = any>(endpoint: string) => apiRequest<T>(endpoint, { method: 'DELETE' }),
};

// ---------------------------------------------------------------------------
// Recruiter Kanban Stages — typed helpers
// ---------------------------------------------------------------------------

export interface JobStage {
  id: string;
  position: number;
  name: string;
}

export interface BoardCandidate {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  applied_at: string;
  resume_url: string;
  stage_id: string | null;
  status: string;
  ai_match_score?: number | null;
  interview?: {
    id: string;
    status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled' | 'expired';
    scheduled_at: string;
    expires_at: string | null;
  } | null;
}

export interface BoardResponse {
  stages: Array<JobStage & { candidates: BoardCandidate[] }>;
  rejected: BoardCandidate[];
}

export interface AutoScheduleAssignment {
  application_id: string;
  day: string;
  expires_at: string;
}

export interface AutoScheduleSkipped {
  application_id: string;
  reason: string;
}

export interface AutoScheduleResponse {
  assigned: AutoScheduleAssignment[];
  skipped: AutoScheduleSkipped[];
}

export const stagesApi = {
  list: (jobId: string) => api.get<JobStage[]>(`/job/${jobId}/stages`),
  create: (jobId: string, body: { name: string; position?: number }) =>
    api.post<JobStage>(`/job/${jobId}/stages`, body),
  rename: (jobId: string, stageId: string, name: string) =>
    apiRequest<JobStage>(`/job/${jobId}/stages/${stageId}`, {
      method: 'PATCH', body: JSON.stringify({ name }),
    }),
  reorder: (jobId: string, items: Array<{ id: string; position: number }>) =>
    api.put<JobStage[]>(`/job/${jobId}/stages/reorder`, items),
  remove: (jobId: string, stageId: string, moveTo?: string) =>
    api.delete<void>(`/job/${jobId}/stages/${stageId}${moveTo ? `?move_to=${moveTo}` : ''}`),
};

export interface BulkMoveSkipped {
  application_id: string;
  reason: 'no_score' | 'below_threshold';
  ai_match_score: number | null;
}

export interface BulkMoveResponse {
  moved: string[];
  skipped: BulkMoveSkipped[];
  target_stage: { id: string; name: string };
}

export const boardApi = {
  get: (jobId: string) => api.get<BoardResponse>(`/job/${jobId}/board`),
  moveCandidate: (jobId: string, applicationId: string, body: { stage_id: string | null; rejected?: boolean }) =>
    apiRequest<BoardCandidate>(`/job/${jobId}/applications/${applicationId}/stage`, {
      method: 'PATCH', body: JSON.stringify(body),
    }),
  bulkMove: (jobId: string, stageId: string, body: { min_score: number; target_stage_id?: string }) =>
    api.post<BulkMoveResponse>(`/job/${jobId}/stages/${stageId}/bulk-move`, body),
  bulkMovePreview: (jobId: string, stageId: string, params: { min_score: number; target_stage_id?: string }) => {
    const qs = new URLSearchParams({
      min_score: String(params.min_score),
      ...(params.target_stage_id ? { target_stage_id: params.target_stage_id } : {}),
    }).toString();
    return api.get<BulkMoveResponse>(`/job/${jobId}/stages/${stageId}/bulk-move/preview?${qs}`);
  },
};

export const autoScheduleApi = {
  run: (jobId: string, body: { stage_id: string; start_date: string; end_date: string }) =>
    api.post<AutoScheduleResponse>(`/job/${jobId}/auto-schedule`, body),
  preview: (jobId: string, params: { stage_id: string; start_date: string; end_date: string }) => {
    const qs = new URLSearchParams(params).toString();
    return api.get<AutoScheduleResponse>(`/job/${jobId}/auto-schedule/preview?${qs}`);
  },
};