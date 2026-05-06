import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock('@/lib/api', () => {
  return {
    boardApi: {
      bulkMovePreview: vi.fn(),
      bulkMove: vi.fn(),
    },
  };
});

import { boardApi } from '@/lib/api';
import { BulkMoveDialog } from '../BulkMoveDialog';

const mockedPreview = boardApi.bulkMovePreview as unknown as ReturnType<typeof vi.fn>;
const mockedMove = boardApi.bulkMove as unknown as ReturnType<typeof vi.fn>;

function renderDialog(
  props: Partial<React.ComponentProps<typeof BulkMoveDialog>> = {},
) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const onMoved = vi.fn();
  const onOpenChange = vi.fn();
  const utils = render(
    <QueryClientProvider client={qc}>
      <BulkMoveDialog
        jobId="job-1"
        sourceStage={{ id: 'stage-a', name: 'Applied' }}
        nextStage={{ id: 'stage-b', name: 'Shortlisted' }}
        open={true}
        onOpenChange={onOpenChange}
        onMoved={onMoved}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { ...utils, onMoved, onOpenChange };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('BulkMoveDialog', () => {
  it('renders preview count from mocked API', async () => {
    mockedPreview.mockResolvedValue({
      moved: ['a', 'b', 'c'],
      skipped: [
        {
          application_id: 'd',
          reason: 'below_threshold',
          ai_match_score: 50,
        },
        { application_id: 'e', reason: 'no_score', ai_match_score: null },
      ],
      target_stage: { id: 'stage-b', name: 'Shortlisted' },
    });
    renderDialog();
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /Move 3/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/Shortlisted/).length).toBeGreaterThan(0);
  });

  it('confirm calls bulkMove once and onMoved once', async () => {
    mockedPreview.mockResolvedValue({
      moved: ['a'],
      skipped: [],
      target_stage: { id: 'stage-b', name: 'Shortlisted' },
    });
    mockedMove.mockResolvedValue({
      moved: ['a'],
      skipped: [],
      target_stage: { id: 'stage-b', name: 'Shortlisted' },
    });
    const { onMoved } = renderDialog();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Move 1/i })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole('button', { name: /Move 1/i }));
    await waitFor(() => expect(mockedMove).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onMoved).toHaveBeenCalledTimes(1));
  });
});
