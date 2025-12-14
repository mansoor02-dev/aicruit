import React from 'react';
import { API_CONFIG } from '@/config/api';

interface ResumeUploadSectionProps {
  resumeFile: File | null;
  uploadStatus: 'idle' | 'uploading' | 'success' | 'error';
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  onUpload: () => void;
  parsedData?: any;
  onParse?: () => void;
  parsing?: boolean;
}

export function ResumeUploadSection({
  resumeFile,
  uploadStatus,
  onFileSelect,
  onDrop,
  onUpload,
  parsedData,
  onParse,
  parsing,
}: ResumeUploadSectionProps) {
  // No parser URL input in UI: parse endpoint is configured in frontend/backend config
  return (
    <section className="mb-10">
      <h2 className="text-2xl font-semibold mb-6 text-blue-700">Upload Your Resume</h2>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        className="border-2 border-dashed border-blue-300 p-8 rounded-2xl flex flex-col items-center justify-center hover:border-blue-500 transition-colors duration-300 bg-gradient-to-br from-white to-blue-50 shadow-lg"
      >
        <p className="mb-2 text-gray-600 text-lg">Drag & drop your resume here</p>
        <p className="text-sm text-gray-400 mb-4">Accepted formats: PDF, DOCX</p>

        {/* Custom Centered File Input */}
        <div className="mb-4 w-full flex justify-center">
          <label className="relative cursor-pointer inline-block w-full max-w-xs">
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={onFileSelect}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            <div className="px-6 py-3 bg-white text-gray-700 border border-gray-300 rounded-full shadow-md hover:bg-gray-100 transition text-center">
              {resumeFile ? resumeFile.name : 'Choose File'}
            </div>
          </label>
        </div>

        <div className="mt-4">
          <button
            className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full font-semibold shadow-md disabled:opacity-50 transition"
            onClick={onUpload}
            disabled={!resumeFile || uploadStatus === 'uploading'}
          >
            {uploadStatus === 'uploading' ? 'Uploading...' : 'Upload Resume'}
          </button>
        </div>

        {uploadStatus === 'success' && (
          <div className="mt-3 text-green-600 font-medium">Resume parsed successfully!</div>
        )}
        {uploadStatus === 'error' && (
          <div className="mt-3 text-red-600 font-medium">Error uploading resume.</div>
        )}

        {/* Parse Resume UI: visible after upload success */}
        {uploadStatus === 'success' && (
          <div className="mt-4 w-full max-w-md">
            <div className="mb-3 text-sm text-gray-600">Parser will be called via configured backend endpoint.</div>
            <div className="flex items-center gap-3">
              <button
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full font-medium shadow-md disabled:opacity-50"
                onClick={() => onParse && onParse()}
                disabled={!parsedData?.id || parsing}
              >
                {parsing ? 'Parsing...' : 'Parse Resume'}
              </button>
              <div>
                {parsedData?.id && (
                  <div className="text-sm text-gray-600">ID: <span className="font-mono">{parsedData.id}</span></div>
                )}
                {parsedData && ((parsedData as any).file_url || (parsedData as any).fileUrl) && (
                  (() => {
                    const raw = (parsedData as any).file_url || (parsedData as any).fileUrl;
                    const url = raw && raw.startsWith('/') ? `${API_CONFIG.BASE_URL}${raw}` : raw;
                    return (
                      <div className="text-sm text-gray-600 mt-1">
                        <a href={url} target="_blank" rel="noopener noreferrer" className="underline text-indigo-600">Open uploaded file</a>
                      </div>
                    );
                  })()
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

