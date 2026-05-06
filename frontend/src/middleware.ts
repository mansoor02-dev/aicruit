import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Get user from cookie (we'll use localStorage on client side, but middleware can check cookies)
  // For now, we'll let client-side handle auth checks since we're using localStorage
  // This middleware can be extended to check server-side auth tokens if needed
  
  return NextResponse.next();
}

export const config = {
  matcher: [
    '/recruiter/:path*',
    '/candidate/:path*',
  ],
};

