import * as React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

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
    autoScheduleApi: {
      preview: vi.fn(),
      run: vi.fn(),
    },
  };
});

import { autoScheduleApi } from '@/lib/api';
import { AutoScheduleDialog } from '../AutoScheduleDialog';

const mockedPreview = autoScheduleApi.preview as unknown as ReturnType<typeof vi.fn>;
const mockedRun = autoScheduleApi.run as unknown as ReturnType<typeof vi.fn>;

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

const STAGES = [
  { id: 's1', position: 0, name: 'Applied' },
  { id: 's2', position: 1, name: 'AI Interview' },
];

// 23 candidates across 5 days → [5,5,5,4,4]
const DISTRIBUTION = [5, 5, 5, 4, 4];
const DAYS = ['2026-05-05', '2026-05-06', '2026-05-07', '2026-05-08', '2026-05-09'];

function buildAssigned() {
  const assigned: Array<{ application_id: string; day: string; expires_at: string }> = [];
  let appCounter = 0;
  DISTRIBUTION.forEach((count, dayIdx) => {
    for (let i = 0; i < count; i++) {
      assigned.push({
        application_id: `app-${appCounter++}`,
        day: DAYS[dayIdx],
        expires_at: `${DAYS[dayIdx]}T23:59:59Z`,
      });
    }
  });
  return assigned;
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedPreview.mockResolvedValue({ assigned: buildAssigned(), skipped: [] });
  mockedRun.mockResolvedValue({ assigned: buildAssigned(), skipped: [] });
});

describe('AutoScheduleDialog', () => {
  it('renders stage dropdown with provided stages', async () => {
    renderWithClient(
      <AutoScheduleDialog
        jobId="job-1"
        stages={STAGES}
        open={true}
        onOpenChange={() => {}}
        onScheduled={() => {}}
      />,
    );

    const select = screen.getByLabelText('Stage') as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    const optionTexts = Array.from(select.options).map((o) => o.textContent);
    expect(optionTexts).toContain('Applied');
    expect(optionTexts).toContain('AI Interview');
  });

  it('shows preview with 5 days and the correct counts for 23/5', async () => {
    const user = userEvent.setup();
    renderWithClient(
      <AutoScheduleDialog
        jobId="job-1"
        stages={STAGES}
        open={true}
        onOpenChange={() => {}}
        onScheduled={() => {}}
      />,
    );

    await user.type(screen.getByLabelText('Start date'), '2026-05-05');
    await user.type(screen.getByLabelText('End date'), '2026-05-09');

    await waitFor(
      () => {
        expect(mockedPreview).toHaveBeenCalled();
      },
      { timeout: 2000 },
    );

    const previewBox = await screen.findByTestId('preview');
    await waitFor(() => {
      expect(previewBox.textContent).toMatch(/Day 1.*5 candidates/);
    });
    expect(previewBox.textContent).toMatch(/Day 2.*5 candidates/);
    expect(previewBox.textContent).toMatch(/Day 3.*5 candidates/);
    expect(previewBox.textContent).toMatch(/Day 4.*4 candidates/);
    expect(previewBox.textContent).toMatch(/Day 5.*4 candidates/);
  });

  it('Confirm calls autoScheduleApi.run and onScheduled', async () => {
    const user = userEvent.setup();
    const onScheduled = vi.fn();
    const onOpenChange = vi.fn();
    renderWithClient(
      <AutoScheduleDialog
        jobId="job-1"
        stages={STAGES}
        open={true}
        onOpenChange={onOpenChange}
        onScheduled={onScheduled}
      />,
    );

    await user.type(screen.getByLabelText('Start date'), '2026-05-05');
    await user.type(screen.getByLabelText('End date'), '2026-05-09');

    // Wait for preview so confirm is enabled
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /confirm/i });
      expect(btn).not.toBeDisabled();
    }, { timeout: 2000 });

    await user.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(mockedRun).toHaveBeenCalledWith('job-1', {
        stage_id: 's1',
        start_date: '2026-05-05',
        end_date: '2026-05-09',
      });
    });
    await waitFor(() => {
      expect(onScheduled).toHaveBeenCalled();
    });
  });
});
