import * as React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('next/link', () => ({
  default: ({ children, href, ...rest }: any) =>
    React.createElement('a', { href, ...rest }, children),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('@/lib/api', async () => {
  class ApiError extends Error {
    status?: number;
    body?: any;
    constructor(message: string, status?: number, body?: any) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.body = body;
    }
  }
  return {
    ApiError,
    boardApi: {
      get: vi.fn(),
      moveCandidate: vi.fn(),
    },
    autoScheduleApi: {
      preview: vi.fn(),
      run: vi.fn(),
    },
  };
});

import { boardApi } from '@/lib/api';
import { KanbanBoard, computeMove } from '../KanbanBoard';
import type { BoardStage } from '../StageColumn';

const mockedGet = boardApi.get as unknown as ReturnType<typeof vi.fn>;

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

const BOARD = {
  stages: [
    {
      id: 's1',
      position: 0,
      name: 'Applied',
      candidates: [
        {
          application_id: 'a1',
          candidate_id: 'c1',
          candidate_name: 'Alice',
          candidate_email: 'alice@example.com',
          applied_at: '2026-05-01T00:00:00Z',
          resume_url: 'http://r/a1.pdf',
          stage_id: 's1',
          status: 'Applied',
          interview: null,
        },
        {
          application_id: 'a2',
          candidate_id: 'c2',
          candidate_name: 'Bob',
          candidate_email: 'bob@example.com',
          applied_at: '2026-05-02T00:00:00Z',
          resume_url: 'http://r/a2.pdf',
          stage_id: 's1',
          status: 'Applied',
          interview: null,
        },
      ],
    },
    {
      id: 's2',
      position: 1,
      name: 'Shortlisted',
      candidates: [
        {
          application_id: 'a3',
          candidate_id: 'c3',
          candidate_name: 'Carol',
          candidate_email: 'carol@example.com',
          applied_at: '2026-05-03T00:00:00Z',
          resume_url: 'http://r/a3.pdf',
          stage_id: 's2',
          status: 'Shortlisted',
          interview: null,
        },
      ],
    },
  ],
  rejected: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedGet.mockResolvedValue(BOARD);
});

describe('KanbanBoard', () => {
  it('renders one column per stage with the right candidate counts', async () => {
    renderWithClient(
      <KanbanBoard jobId="job-1" aiInterviewEnabled={false} />,
    );

    await waitFor(() => {
      expect(screen.getByText('Applied')).toBeInTheDocument();
    });
    expect(screen.getByText('Shortlisted')).toBeInTheDocument();

    const col1 = screen.getByTestId('stage-column-s1');
    const col2 = screen.getByTestId('stage-column-s2');
    expect(col1.textContent).toContain('2');
    expect(col2.textContent).toContain('1');

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('Carol')).toBeInTheDocument();
  });

  it('does NOT render the Auto-schedule button when ai is disabled', async () => {
    renderWithClient(
      <KanbanBoard jobId="job-1" aiInterviewEnabled={false} />,
    );
    await waitFor(() => expect(screen.getByText('Applied')).toBeInTheDocument());
    expect(screen.queryByTestId('auto-schedule-button')).not.toBeInTheDocument();
  });

  it('renders the Auto-schedule button when ai is enabled', async () => {
    renderWithClient(
      <KanbanBoard jobId="job-1" aiInterviewEnabled={true} />,
    );
    await waitFor(() => expect(screen.getByText('Applied')).toBeInTheDocument());
    expect(screen.getByTestId('auto-schedule-button')).toBeInTheDocument();
  });
});

describe('computeMove', () => {
  const stages: BoardStage[] = BOARD.stages as BoardStage[];
  const aliceCandidate = BOARD.stages[0].candidates[0];

  it('returns stage move when dropped on a stage container', () => {
    const result = computeMove(aliceCandidate as any, 'stage:s2', stages);
    expect(result).toEqual({ stage_id: 's2', rejected: false });
  });

  it('returns rejected move when dropped on the rejected lane', () => {
    const result = computeMove(aliceCandidate as any, 'rejected', stages);
    expect(result).toEqual({ stage_id: 's1', rejected: true });
  });

  it('returns null when overId is null/undefined', () => {
    expect(computeMove(aliceCandidate as any, null, stages)).toBeNull();
    expect(computeMove(aliceCandidate as any, undefined, stages)).toBeNull();
  });

  it('resolves over-candidate id to that candidate stage', () => {
    const result = computeMove(aliceCandidate as any, 'a3', stages);
    expect(result).toEqual({ stage_id: 's2', rejected: false });
  });
});
