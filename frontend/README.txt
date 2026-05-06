================================================================================
                    HARVEST AI HIRE - PROJECT DOCUMENTATION
================================================================================

PROJECT OVERVIEW
----------------
This is an AI-Powered Recruitment Platform (AIcruit) built with Next.js. 
The platform provides separate interfaces for Recruiters and Candidates to 
manage job postings, applications, and the hiring process.

TECHNOLOGY STACK
----------------
- Framework: Next.js 14 (App Router)
- Language: TypeScript
- Styling: Tailwind CSS
- UI Components: Shadcn UI (Radix UI primitives)
- State Management: React Context API (AuthContext)
- Data Fetching: TanStack React Query
- Icons: Lucide React
- Charts: Recharts
- Forms: React Hook Form with Zod validation

PROJECT STRUCTURE
-----------------
harvest-ai-hire-main/
├── src/
│   ├── app/                          # Next.js App Router directory
│   │   ├── layout.tsx                # Root layout with providers
│   │   ├── page.tsx                  # Home page (Auth redirect)
│   │   ├── providers.tsx             # Client-side providers wrapper
│   │   ├── not-found.tsx              # 404 page
│   │   ├── recruiter/                # Recruiter routes
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx          # Analytics dashboard
│   │   │   ├── jobs/
│   │   │   │   ├── page.tsx          # Jobs list
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx      # Job details (dynamic route)
│   │   │   ├── candidates/
│   │   │   │   └── page.tsx          # All candidates view
│   │   │   └── settings/
│   │   │       └── page.tsx          # Company settings
│   │   └── candidate/                # Candidate routes
│   │       ├── jobs/
│   │       │   └── page.tsx          # Browse jobs
│   │       ├── applications/
│   │       │   └── page.tsx          # My applications
│   │       └── profile/
│   │           └── page.tsx          # Candidate profile
│   ├── components/
│   │   ├── Auth.tsx                  # Authentication component
│   │   ├── NavLink.tsx               # Next.js navigation link
│   │   ├── layout/
│   │   │   ├── RecruiterLayout.tsx   # Recruiter sidebar layout
│   │   │   └── CandidateLayout.tsx   # Candidate header layout
│   │   ├── dashboard/
│   │   │   └── StatsCard.tsx         # Dashboard statistics card
│   │   └── ui/                       # Shadcn UI components
│   ├── contexts/
│   │   └── AuthContext.tsx            # Authentication context
│   ├── data/
│   │   └── mockData.ts               # Mock data for development
│   ├── hooks/
│   │   ├── use-mobile.tsx
│   │   └── use-toast.ts
│   ├── lib/
│   │   └── utils.ts                  # Utility functions
│   ├── index.css                     # Global styles
│   └── middleware.ts                 # Next.js middleware
├── public/                            # Static assets
├── next.config.js                     # Next.js configuration
├── tailwind.config.ts                 # Tailwind CSS configuration
├── tsconfig.json                      # TypeScript configuration
└── package.json                       # Dependencies

ROUTING STRUCTURE
------------------
Next.js uses file-based routing in the app directory:

PUBLIC ROUTES:
- /                          → Auth page (redirects if authenticated)

RECRUITER ROUTES (Protected):
- /recruiter/dashboard       → Analytics overview with charts and stats
- /recruiter/job            → Job postings management
- /recruiter/job/[id]       → Individual job details with applicant kanban
- /recruiter/candidates      → All candidates across all jobs
- /recruiter/settings        → Company profile, team, billing, notifications

CANDIDATE ROUTES (Protected):
- /candidate/job            → Browse and search available jobs
- /candidate/applications    → Track application status
- /candidate/profile         → Edit profile, upload resume, manage skills

AUTHENTICATION FLOW
-------------------
1. User visits root route (/)
2. If not authenticated → Shows Auth component (login/signup)
3. User selects role (Recruiter or Candidate)
4. After login/signup → Redirects based on role:
   - RECRUITER → /recruiter/dashboard
   - CANDIDATE → /candidate/job
5. Auth state stored in localStorage (client-side only)
6. Protected routes check authentication via AuthContext

AUTHENTICATION CONTEXT
----------------------
Location: src/contexts/AuthContext.tsx

Features:
- User login/signup (mock implementation)
- Role-based access (RECRUITER | CANDIDATE)
- localStorage persistence
- Client-side only (marked with 'use client')

User Object Structure:
{
  id: string
  email: string
  name: string
  role: 'RECRUITER' | 'CANDIDATE'
  avatar?: string
}

PROTECTED ROUTES
----------------
Routes are protected at the component level using AuthContext:
- Each page component checks authentication status
- Unauthenticated users are redirected to home (/)
- Role-based access ensures users only see their respective routes

LAYOUTS
-------
1. RecruiterLayout (src/components/layout/RecruiterLayout.tsx)
   - Sidebar navigation with:
     * Overview (Dashboard)
     * Jobs
     * Candidates
     * Settings
   - Top bar with search and user menu
   - Logout functionality

2. CandidateLayout (src/components/layout/CandidateLayout.tsx)
   - Top navigation bar with:
     * Browse Jobs
     * My Applications
     * Profile
   - Search bar
   - User dropdown menu

KEY FEATURES
------------

RECRUITER FEATURES:
1. Dashboard:
   - Analytics overview with charts
   - Total applicants, interviews, AI match scores
   - Recent jobs and scheduled interviews
   - Monthly applicant trends

2. Jobs Management:
   - Create new job postings
   - View all jobs in table format
   - Search and filter jobs
   - Job status management (Draft, Open, Closed)

3. Job Details:
   - Kanban board for applicant tracking
   - Status columns: Applied, Screening, Interview, Offered, Rejected
   - AI match scores for each candidate
   - Schedule interviews
   - View candidate resumes

4. Candidates:
   - View all candidates across all jobs
   - Search by name, email, or job title
   - AI match score display
   - Application status tracking

5. Settings:
   - Company profile management
   - Team member management
   - Billing and subscription
   - Notification preferences

CANDIDATE FEATURES:
1. Browse Jobs:
   - Search by title or skills
   - Filter by location type (Remote, Onsite, Hybrid)
   - Filter by experience level
   - Quick apply functionality
   - Job card display with key details

2. Applications:
   - Track application status
   - View interview schedules
   - Application history

3. Profile:
   - Edit personal information
   - Upload resume
   - Add/remove skills
   - LinkedIn profile link
   - Bio/description

INSTALLATION & SETUP
--------------------
1. Install dependencies:
   npm install
   # or
   yarn install
   # or
   pnpm install

2. Run development server:
   npm run dev
   # or
   yarn dev
   # or
   pnpm dev

3. Open browser:
   http://localhost:3000

4. Build for production:
   npm run build
   npm start

ENVIRONMENT SETUP
-----------------
No environment variables required for basic functionality.
The project uses mock data and localStorage for authentication.

For production, you would need to:
- Set up a backend API
- Configure environment variables for API endpoints
- Set up database connections
- Configure authentication service (JWT, OAuth, etc.)

DEPENDENCIES
------------
Core:
- next: ^14.2.0
- react: ^18.3.1
- react-dom: ^18.3.1
- typescript: ^5.8.3

UI & Styling:
- tailwindcss: ^3.4.17
- @radix-ui/*: Various UI primitives
- lucide-react: ^0.462.0
- recharts: ^2.15.4

State & Data:
- @tanstack/react-query: ^5.83.0
- react-hook-form: ^7.61.1
- zod: ^3.25.76

Utilities:
- clsx: ^2.1.1
- tailwind-merge: ^2.6.0
- date-fns: ^3.6.0

DEVELOPMENT NOTES
-----------------
1. All pages are client components ('use client') because they use:
   - React hooks (useState, useEffect)
   - Context API (useAuth)
   - Browser APIs (localStorage)

2. The root layout (app/layout.tsx) is a server component that wraps
   everything with client-side providers.

3. Navigation uses Next.js Link component instead of react-router-dom.

4. Dynamic routes use [id] folder structure in Next.js App Router.

5. Middleware (src/middleware.ts) can be extended for server-side
   route protection if needed.

MOCK DATA
---------
Location: src/data/mockData.ts

Contains:
- mockJobs: Array of job postings
- mockApplicants: Array of candidate applications
- mockInterviews: Scheduled interview data
- analyticsData: Chart data for dashboard

DATA FLOW
---------
1. User Authentication:
   AuthContext → localStorage → Component state

2. Job Management:
   Component state → UI → Mock data (will be API calls in production)

3. Application Tracking:
   Component state → UI → Mock data

FUTURE ENHANCEMENTS
-------------------
1. Backend Integration:
   - Replace mock data with API calls
   - Implement real authentication
   - Database integration

2. Features:
   - Real-time notifications
   - Email integration
   - Resume parsing with AI
   - Advanced search and filtering
   - Interview scheduling with calendar integration
   - Video interview support
   - AI-powered candidate matching

3. Performance:
   - Server-side rendering for public pages
   - Image optimization
   - Code splitting
   - Caching strategies

4. Security:
   - Server-side route protection
   - JWT token management
   - CSRF protection
   - Input validation and sanitization

TROUBLESHOOTING
---------------
1. Build Errors:
   - Ensure all 'use client' directives are present on client components
   - Check TypeScript types are correct
   - Verify all imports are valid

2. Routing Issues:
   - Ensure page.tsx files are in correct directories
   - Check dynamic route syntax [id] for parameterized routes

3. Styling Issues:
   - Verify Tailwind config includes all source paths
   - Check CSS imports in layout.tsx

4. Authentication Issues:
   - Clear localStorage if auth state is corrupted
   - Check browser console for errors

CONTACT & SUPPORT
-----------------
This project was converted from a React (Vite) application to Next.js.
For issues or questions, refer to:
- Next.js Documentation: https://nextjs.org/docs
- React Documentation: https://react.dev
- Tailwind CSS: https://tailwindcss.com/docs

================================================================================
                              END OF DOCUMENTATION
================================================================================

