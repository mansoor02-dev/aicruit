'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

interface InterviewDetail {
  question_order: number;
  category: string;
  question_text: string;
  transcript: string | null;
  ai_score: number | null;
  confidence_score: number | null;
  sentiment: string | null;
  audio_url: string | null;
  video_url: string | null;
}

interface CategoryScore {
  category: string;
  score: number;
}

interface ReportData {
  overall_score: number;
  category_scores: CategoryScore[];
  overall_remark: string;
  strengths: string[];
  improvements: string[];
}

interface InterviewData {
  interview_id: string;
  status: string;
  scheduled_at: string;
  details: InterviewDetail[];
  report?: ReportData | null;
}

export default function InterviewDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  
  const [data, setData] = useState<InterviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        setLoading(true);
        const res = await api.get(`/interview/${id}/details`);
        setData(res);
      } catch (err: any) {
        console.error("Failed to fetch interview details:", err);
        setError("Could not load details. Make sure the interview exists and you have permissions.");
      } finally {
        setLoading(false);
      }
    };

    fetchDetails();
  }, [id]);

  if (loading) {
    return (
      <RecruiterLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      </RecruiterLayout>
    );
  }

  if (error || !data) {
    return (
      <RecruiterLayout>
        <div className="text-center py-12 space-y-4">
          <p className="text-destructive">{error || "Interview details not found."}</p>
          <Button onClick={() => router.back()}>Go Back</Button>
        </div>
      </RecruiterLayout>
    );
  }

  return (
    <RecruiterLayout>
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Interview Analysis</h1>
            <p className="text-muted-foreground flex items-center gap-2 mt-1">
              Status: <Badge variant="outline">{data.status}</Badge> •
              Scheduled: {new Date(data.scheduled_at).toLocaleString()}
            </p>
          </div>
        </div>

        {/* AI Report Card */}
        {data.report && (
          <Card className="bg-card">
            <CardHeader>
              <CardTitle className="flex justify-between items-center">
                <span>AI Final Report</span>
                <Badge variant="default" className="text-lg py-1 px-3">Overall Score: {data.report.overall_score}/10</Badge>
              </CardTitle>
              <CardDescription>Generated assessment based on logic, communication, and technical correctness.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              
              <div className="space-y-2">
                <h3 className="font-semibold text-foreground border-b pb-2">Overall Evaluator Remarks</h3>
                <p className="text-muted-foreground whitespace-pre-wrap">{data.report.overall_remark}</p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Strengths */}
                <div className="space-y-3">
                  <h3 className="font-semibold text-foreground border-b pb-2">Strengths</h3>
                  <ul className="list-disc pl-5 space-y-2 text-muted-foreground">
                    {data.report.strengths.map((str, idx) => (
                      <li key={idx}>{str}</li>
                    ))}
                  </ul>
                </div>
                {/* Improvements */}
                <div className="space-y-3">
                  <h3 className="font-semibold text-foreground border-b pb-2">Areas for Improvement</h3>
                  <ul className="list-disc pl-5 space-y-2 text-muted-foreground">
                    {data.report.improvements.map((imp, idx) => (
                      <li key={idx}>{imp}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Category Breakdown */}
              <div className="space-y-3 pt-4">
                <h3 className="font-semibold text-foreground border-b pb-2">Category Breakdown</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {data.report.category_scores.map((cat, idx) => (
                    <div key={idx} className="bg-muted p-4 rounded-lg space-y-2 border">
                      <div className="flex justify-between items-center">
                        <span className="font-medium text-sm">{cat.category}</span>
                        <span className="text-sm font-bold">{cat.score.toFixed(1)}/10</span>
                      </div>
                      <div className="h-2 w-full bg-background rounded-full overflow-hidden">
                        <div 
                           className="h-full bg-primary" 
                           style={{ width: `${(cat.score / 10) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            </CardContent>
          </Card>
        )}

        {/* Details Table Card */}
        <Card className="bg-card">
          <CardHeader>
             <CardTitle>Q&A Transcript</CardTitle>
             <CardDescription>
                Detailed breakdown of each question, the candidate's transcript, and AI evaluation. Drag the column dividers to resize.
             </CardDescription>
          </CardHeader>
          <CardContent>
            {/* 
              Wrap the table in a container that allows horizontal scrolling.
              The th/td tags use a combination of min-width to ensure they are broad enough, 
              but style components handle raw 'resize: horizontal' which is great for dragging.
            */}
            <div className="w-full overflow-x-auto border rounded-md custom-scrollbar">
              <table className="w-full text-sm text-left border-collapse" style={{ tableLayout: 'auto' }}>
                <thead className="bg-muted text-muted-foreground border-b uppercase text-xs">
                  <tr>
                    <th className="px-4 py-3 font-semibold border-r" style={{ resize: 'horizontal', overflow: 'hidden', minWidth: '60px' }}>#</th>
                    <th className="px-4 py-3 font-semibold border-r" style={{ resize: 'horizontal', overflow: 'hidden', minWidth: '120px' }}>Category</th>
                    <th className="px-4 py-3 font-semibold border-r" style={{ resize: 'horizontal', overflow: 'hidden', minWidth: '250px' }}>Question</th>
                    <th className="px-4 py-3 font-semibold border-r" style={{ resize: 'horizontal', overflow: 'hidden', minWidth: '300px' }}>Candidate Answer</th>
                    <th className="px-4 py-3 font-semibold border-r" style={{ resize: 'horizontal', overflow: 'hidden', minWidth: '100px' }}>AI Score %</th>
                    <th className="px-4 py-3 font-semibold border-r" style={{ resize: 'horizontal', overflow: 'hidden', minWidth: '100px' }}>Confidence %</th>
                    <th className="px-4 py-3 font-semibold" style={{ resize: 'horizontal', overflow: 'hidden', minWidth: '250px' }}>Evaluator Remarks</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.details.map((row) => (
                    <tr key={row.question_order} className="hover:bg-muted/50 transition-colors">
                      <td className="px-4 py-3 align-top border-r font-medium">{row.question_order}</td>
                      <td className="px-4 py-3 align-top border-r text-muted-foreground">{row.category || 'Intro'}</td>
                      <td className="px-4 py-3 align-top border-r text-foreground">{row.question_text}</td>
                      <td className="px-4 py-3 align-top border-r whitespace-pre-wrap">{row.transcript || <span className="text-muted-foreground italic">No Answer Recorded</span>}</td>
                      <td className="px-4 py-3 align-top border-r">
                        {row.ai_score !== null ? (
                           <Badge variant={row.ai_score >= 70 ? 'default' : (row.ai_score >= 50 ? 'secondary' : 'destructive')}>
                             {row.ai_score}%
                           </Badge>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3 align-top border-r">{row.confidence_score !== null ? `${row.confidence_score}%` : '—'}</td>
                      <td className="px-4 py-3 align-top whitespace-pre-wrap">{row.sentiment || '—'}</td>
                    </tr>
                  ))}
                  {data.details.length === 0 && (
                     <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">No questions found for this interview.</td>
                     </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Small inline style inject for the scrollbar polish */}
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: #334155;
          border-radius: 4px;
        }
      `}} />
    </RecruiterLayout>
  );
}
