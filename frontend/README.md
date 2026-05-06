# Harvest AI Hire - AI-Powered Recruitment Platform

## Project Overview

Harvest AI Hire is a modern recruitment platform built with Next.js that helps recruiters manage job postings and candidates find their next opportunity. The platform features AI-powered candidate matching, comprehensive analytics, and an intuitive interface for both recruiters and candidates.

## Technologies

This project is built with:

- **Next.js 14** (App Router)
- **TypeScript**
- **React 18**
- **shadcn-ui** (Radix UI components)
- **Tailwind CSS**
- **TanStack React Query**
- **Recharts** (for analytics)

## Getting Started

### Prerequisites

- Node.js 18+ and npm (or yarn/pnpm)
- Git

### Installation

```sh
# Step 1: Clone the repository
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory
cd harvest-ai-hire-main

# Step 3: Install dependencies
npm install

# Step 4: Start the development server
npm run dev
```

The application will be available at `http://localhost:3000`

### Build for Production

```sh
npm run build
npm start
```

## Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── recruiter/         # Recruiter dashboard routes
│   └── candidate/         # Candidate routes
├── components/            # Reusable React components
│   ├── layout/           # Layout components
│   └── ui/               # UI components (shadcn)
├── contexts/             # React Context providers
├── data/                 # Mock data
├── hooks/                # Custom React hooks
└── lib/                  # Utility functions
```

## Features

### For Recruiters
- **Dashboard**: Analytics overview with charts and statistics
- **Job Management**: Create, edit, and manage job postings
- **Candidate Tracking**: Kanban board for applicant pipeline
- **AI Matching**: View AI-powered candidate match scores
- **Settings**: Company profile, team management, and billing

### For Candidates
- **Job Search**: Browse and filter available positions
- **Quick Apply**: One-click job applications
- **Application Tracking**: Monitor application status
- **Profile Management**: Upload resume and manage skills

## Development

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint

## Deployment

This project can be deployed to any platform that supports Next.js:

- **Vercel** (recommended)
- **Netlify**
- **AWS Amplify**
- **Railway**
- **Any Node.js hosting**

For Vercel deployment:
1. Push your code to GitHub
2. Import the repository in Vercel
3. Deploy automatically

## Custom Domain

You can connect a custom domain to your deployed application through your hosting provider's domain settings.

## License

Private project - All rights reserved
