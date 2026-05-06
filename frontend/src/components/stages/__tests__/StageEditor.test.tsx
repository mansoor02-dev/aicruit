import * as React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

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
    stagesApi: {
      list: vi.fn(),
      create: vi.fn(),
      rename: vi.fn(),
      reorder: vi.fn(),
      remove: vi.fn(),
    },
  };
});

import { stagesApi, ApiError } from '@/lib/api';
import { StageEditor } from '../StageEditor';

const mockedList = stagesApi.list as unknown as ReturnType<typeof vi.fn>;
const mockedCreate = stagesApi.create as unknown as ReturnType<typeof vi.fn>;
const mockedRename = stagesApi.rename as unknown as ReturnType<typeof vi.fn>;
const mockedRemove = stagesApi.remove as unknown as ReturnType<typeof vi.fn>;

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
  { id: 's2', position: 1, name: 'Phone Screen' },
  { id: 's3', position: 2, name: 'Final' },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockedList.mockResolvedValue(STAGES);
  mockedCreate.mockResolvedValue({ id: 'new', position: 3, name: 'X' });
  mockedRename.mockResolvedValue({ id: 's1', position: 0, name: 'Renamed' });
  mockedRemove.mockResolvedValue(undefined);
});

describe('StageEditor', () => {
  it('renders one badge per fetched stage in order', async () => {
    renderWithClient(<StageEditor jobId="job-1" />);

    await waitFor(() => {
      expect(screen.getByText('Applied')).toBeInTheDocument();
    });
    expect(screen.getByText('Phone Screen')).toBeInTheDocument();
    expect(screen.getByText('Final')).toBeInTheDocument();

    const chips = [
      screen.getByTestId('stage-chip-s1'),
      screen.getByTestId('stage-chip-s2'),
      screen.getByTestId('stage-chip-s3'),
    ];
    expect(within(chips[0]).getByText('Applied')).toBeInTheDocument();
    expect(within(chips[1]).getByText('Phone Screen')).toBeInTheDocument();
    expect(within(chips[2]).getByText('Final')).toBeInTheDocument();
  });

  it('Add stage button calls create with the next unused suggestion', async () => {
    const user = userEvent.setup();
    renderWithClient(<StageEditor jobId="job-1" />);

    await waitFor(() => expect(screen.getByText('Applied')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /add stage/i }));

    await waitFor(() => {
      expect(mockedCreate).toHaveBeenCalledWith('job-1', { name: 'AI Interview' });
    });
  });

  it('clicking a badge name allows inline edit; Enter calls rename', async () => {
    const user = userEvent.setup();
    renderWithClient(<StageEditor jobId="job-1" />);

    await waitFor(() => expect(screen.getByText('Applied')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /rename stage applied/i }));

    const input = await screen.findByLabelText('Rename Applied');
    await user.clear(input);
    await user.type(input, 'New Name{Enter}');

    await waitFor(() => {
      expect(mockedRename).toHaveBeenCalledWith('job-1', 's1', 'New Name');
    });
  });

  it('hovering a badge and clicking X opens DeleteStageDialog on 409 with candidate_count', async () => {
    const user = userEvent.setup();
    mockedRemove.mockRejectedValueOnce(
      new (ApiError as any)('Stage has candidates', 409, { candidate_count: 3 }),
    );

    renderWithClient(<StageEditor jobId="job-1" />);

    await waitFor(() => expect(screen.getByText('Applied')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: /delete applied/i }));

    await waitFor(() => {
      expect(screen.getByText(/3 candidates are in stage/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /move and delete/i })).toBeInTheDocument();
  });
});
