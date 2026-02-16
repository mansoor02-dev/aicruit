export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  type: 'Remote' | 'Onsite' | 'Hybrid';
  experienceLevel: 'Junior' | 'Mid-level' | 'Senior' | 'Lead';
  salaryMin: number;
  salaryMax: number;
  requiredSkills: string[];
  description: string;
  status: 'Open' | 'Closed' | 'Draft';
  applicants: number;
  createdAt: string;
}

export interface Applicant {
  id: string;
  name: string;
  email: string;
  jobId: string;
  aiMatchScore: number;
  status: 'Applied' | 'Screening' | 'Interview' | 'Offered' | 'Rejected';
  resumeUrl?: string;
  appliedAt: string;
}

export interface Interview {
  id: string;
  candidateName: string;
  jobTitle: string;
  scheduledAt: string;
  status: 'scheduled' | 'completed' | 'cancelled';
}

export const mockJobs: Job[] = [
  {
    id: '1',
    title: 'Senior Frontend Developer',
    company: 'TechCorp',
    location: 'San Francisco, CA',
    type: 'Remote',
    experienceLevel: 'Senior',
    salaryMin: 120000,
    salaryMax: 180000,
    requiredSkills: ['React', 'TypeScript', 'Node.js', 'GraphQL'],
    description: 'We are looking for a Senior Frontend Developer to join our growing team...',
    status: 'Open',
    applicants: 45,
    createdAt: '2024-01-15',
  },
  {
    id: '2',
    title: 'Product Manager',
    company: 'TechCorp',
    location: 'New York, NY',
    type: 'Hybrid',
    experienceLevel: 'Mid-level',
    salaryMin: 100000,
    salaryMax: 150000,
    requiredSkills: ['Agile', 'Product Strategy', 'Data Analysis', 'Roadmapping'],
    description: 'Join our product team to help shape the future of our platform...',
    status: 'Open',
    applicants: 32,
    createdAt: '2024-01-12',
  },
  {
    id: '3',
    title: 'UX Designer',
    company: 'TechCorp',
    location: 'Los Angeles, CA',
    type: 'Remote',
    experienceLevel: 'Mid-level',
    salaryMin: 90000,
    salaryMax: 130000,
    requiredSkills: ['Figma', 'User Research', 'Prototyping', 'Design Systems'],
    description: 'We need a creative UX Designer to help build beautiful user experiences...',
    status: 'Open',
    applicants: 28,
    createdAt: '2024-01-10',
  },
  {
    id: '4',
    title: 'Backend Engineer',
    company: 'TechCorp',
    location: 'Austin, TX',
    type: 'Onsite',
    experienceLevel: 'Senior',
    salaryMin: 130000,
    salaryMax: 190000,
    requiredSkills: ['Python', 'AWS', 'PostgreSQL', 'Docker'],
    description: 'Looking for a Backend Engineer to build scalable APIs...',
    status: 'Draft',
    applicants: 0,
    createdAt: '2024-01-08',
  },
];

export const mockApplicants: Applicant[] = [
  {
    id: '1',
    name: 'Alice Johnson',
    email: 'alice@example.com',
    jobId: '1',
    aiMatchScore: 92,
    status: 'Interview',
    resumeUrl: '#',
    appliedAt: '2024-01-16',
  },
  {
    id: '2',
    name: 'Bob Smith',
    email: 'bob@example.com',
    jobId: '1',
    aiMatchScore: 87,
    status: 'Screening',
    resumeUrl: '#',
    appliedAt: '2024-01-17',
  },
  {
    id: '3',
    name: 'Carol White',
    email: 'carol@example.com',
    jobId: '1',
    aiMatchScore: 78,
    status: 'Applied',
    resumeUrl: '#',
    appliedAt: '2024-01-18',
  },
  {
    id: '4',
    name: 'David Brown',
    email: 'david@example.com',
    jobId: '2',
    aiMatchScore: 85,
    status: 'Offered',
    resumeUrl: '#',
    appliedAt: '2024-01-13',
  },
  {
    id: '5',
    name: 'Eva Martinez',
    email: 'eva@example.com',
    jobId: '2',
    aiMatchScore: 65,
    status: 'Rejected',
    resumeUrl: '#',
    appliedAt: '2024-01-14',
  },
];

export const mockInterviews: Interview[] = [
  {
    id: '1',
    candidateName: 'Alice Johnson',
    jobTitle: 'Senior Frontend Developer',
    scheduledAt: '2024-01-22T10:00:00',
    status: 'scheduled',
  },
  {
    id: '2',
    candidateName: 'Michael Chen',
    jobTitle: 'Product Manager',
    scheduledAt: '2024-01-22T14:00:00',
    status: 'scheduled',
  },
  {
    id: '3',
    candidateName: 'Sarah Davis',
    jobTitle: 'UX Designer',
    scheduledAt: '2024-01-23T11:00:00',
    status: 'scheduled',
  },
];

export const analyticsData = {
  totalApplicants: 36250,
  newApplicants: 22400,
  rejectedApplications: 11000,
  acceptedApplications: 85,
  monthlyData: [
    { month: 'Jan', applicants: 2800 },
    { month: 'Feb', applicants: 3200 },
    { month: 'Mar', applicants: 2900 },
    { month: 'Apr', applicants: 3500 },
    { month: 'May', applicants: 4100 },
    { month: 'Jun', applicants: 3800 },
    { month: 'Jul', applicants: 4500 },
    { month: 'Aug', applicants: 4200 },
    { month: 'Sep', applicants: 3900 },
    { month: 'Oct', applicants: 4800 },
    { month: 'Nov', applicants: 5200 },
    { month: 'Dec', applicants: 4600 },
  ],
};
