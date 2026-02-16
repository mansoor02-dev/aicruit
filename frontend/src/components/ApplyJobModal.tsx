'use client';

import { useState, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { Upload, Loader2, CheckCircle } from 'lucide-react';
import { api } from '@/lib/api';

interface ApplyJobModalProps {
  jobId: string;
  jobTitle: string;
  isOpen: boolean;
  onClose: () => void;
  onApplySuccess: () => void;
}

interface UploadResponse {
  status: string;
  file_url: string;
  message: string;
  id: string;
}

export function ApplyJobModal({
  jobId,
  jobTitle,
  isOpen,
  onClose,
  onApplySuccess,
}: ApplyJobModalProps) {
  const [uploadedFile, setUploadedFile] = useState<{
    name: string;
    url: string;
  } | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragAreaRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const handleFileSelect = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast({
        title: 'Invalid file type',
        description: 'Please upload a PDF resume',
        variant: 'destructive',
      });
      return;
    }

    await uploadResume(file);
  };

  const uploadResume = async (file: File) => {
    try {
      setIsUploading(true);
      const formData = new FormData();
      formData.append('file', file);
      formData.append('file_type', 'Resume');

      const response = await fetch('http://localhost:8005/upload-file', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const data: UploadResponse = await response.json();
      setUploadedFile({
        name: file.name,
        url: data.file_url,
      });

      toast({
        title: 'Resume uploaded',
        description: 'Your resume has been uploaded successfully',
      });
    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: 'Upload failed',
        description: 'Failed to upload resume. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    dragAreaRef.current?.classList.add('bg-accent');
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    dragAreaRef.current?.classList.remove('bg-accent');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragAreaRef.current?.classList.remove('bg-accent');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleApply = async () => {
    if (!uploadedFile) {
      toast({
        title: 'Resume required',
        description: 'Please upload a resume before applying',
        variant: 'destructive',
      });
      return;
    }

    try {
      setIsApplying(true);
      const applyResponse = await api.post('/job/apply', {
        job_id: jobId,
        resume_url: uploadedFile.url,
      });

      toast({
        title: 'Application submitted',
        description: 'Your application has been sent successfully!',
      });

      onApplySuccess();
      handleClose();
    } catch (error) {
      console.error('Apply error:', error);
      toast({
        title: 'Application failed',
        description: 'Failed to submit application. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsApplying(false);
    }
  };

  const handleClose = () => {
    setUploadedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Apply to {jobTitle}</DialogTitle>
          <DialogDescription>
            Upload your resume to apply for this position
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {uploadedFile ? (
            <div className="flex items-center gap-3 p-4 bg-accent/50 rounded-lg border-2 border-dashed border-primary">
              <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {uploadedFile.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  Ready to apply
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setUploadedFile(null)}
                className="text-xs"
              >
                Change
              </Button>
            </div>
          ) : (
            <div
              ref={dragAreaRef}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className="border-2 border-dashed border-muted-foreground/30 rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground mb-1">
                Drag and drop your resume
              </p>
              <p className="text-xs text-muted-foreground mb-3">
                or click to browse
              </p>
              <p className="text-xs text-muted-foreground">
                PDF files only
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileInputChange}
                className="hidden"
              />
            </div>
          )}

          {isUploading && (
            <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              Uploading resume...
            </div>
          )}
        </div>

        <DialogFooter className="flex gap-2 sm:gap-0">
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleApply}
            disabled={!uploadedFile || isApplying || isUploading}
          >
            {isApplying && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {isApplying ? 'Applying...' : 'Apply Now'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
