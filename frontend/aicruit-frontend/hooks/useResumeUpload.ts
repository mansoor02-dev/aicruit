import { useState } from 'react';
import type { ParsedResumeData } from '@/types';
import { uploadResume, parseResume } from '@/lib/api/resume';
import { API_CONFIG } from '@/config/api';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export function useResumeUpload() {
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [parsedData, setParsedData] = useState<ParsedResumeData | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [parsing, setParsing] = useState<boolean>(false);

  const handleFile = (file: File) => {
    const allowed = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    if (!allowed.includes(file.type)) {
      setErrorMsg('Only PDF or DOCX files are allowed.');
      return;
    }
    setResumeFile(file);
    setErrorMsg(null);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleUpload = async () => {
    if (!resumeFile) return;

    setUploadStatus('uploading');
    setErrorMsg(null);

    try {
      const data = await uploadResume(resumeFile);
      setParsedData(data);
      setUploadStatus('success');
    } catch (err) {
      console.error(err);
      setUploadStatus('error');
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleParse = async (parserUrl?: string) => {
    if (!parsedData?.id) {
      setErrorMsg('No uploaded resume id available');
      return;
    }

    setParsing(true);
    setErrorMsg(null);
    try {
      // Normalize file URL: if backend returned a relative path (starts with '/'), prefix with BASE_URL
      const rawFileUrl = (parsedData as any).file_url || (parsedData as any).fileUrl || '';
      let absoluteFileUrl = rawFileUrl;
      if (rawFileUrl && rawFileUrl.startsWith('/')) {
        absoluteFileUrl = `${rawFileUrl}`;
      }

      const parsed = await parseResume(parsedData.id, parserUrl, absoluteFileUrl);
      setParsedData(parsed);
    } catch (err) {
      console.error(err);
      setErrorMsg(err instanceof Error ? err.message : 'Parse failed');
    } finally {
      setParsing(false);
    }
  };

  const reset = () => {
    setResumeFile(null);
    setUploadStatus('idle');
    setParsedData(null);
    setErrorMsg(null);
  };

  return {
    resumeFile,
    uploadStatus,
    parsedData,
    errorMsg,
    parsing,
    handleFileSelect,
    handleDrop,
    handleUpload,
    handleParse,
    reset,
  };
}

