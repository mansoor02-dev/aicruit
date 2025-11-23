import React from 'react';

interface ErrorDisplayProps {
  errorMsg: string | null;
}

export function ErrorDisplay({ errorMsg }: ErrorDisplayProps) {
  if (!errorMsg) return null;

  return (
    <div className="mt-4 text-red-600 font-medium">{errorMsg}</div>
  );
}

