'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';

export type UserRole = 'RECRUITER' | 'CANDIDATE' | null;

interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  avatar?: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string, role: UserRole) => Promise<void>;
  signup: (email: string, password: string, name: string, role: UserRole, phone?: string, companyName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('aicruit_user');
      return stored ? JSON.parse(stored) : null;
    }
    return null;
  });

  const login = async (email: string, password: string, role: UserRole) => {
    try {
      const response = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const user: User = {
          id: data.user_profile.id,
          email,
          name: data.user_profile.name,
          role: data.user_profile.role as UserRole,
          avatar: undefined
        };
        setUser(user);
        if (typeof window !== 'undefined') {
          localStorage.setItem('aicruit_user', JSON.stringify(user));
          localStorage.setItem('aicruit_tokens', JSON.stringify({
            access_token: data.access_token,
            refresh_token: data.refresh_token,
          }));
        }
      } else {
        const error = await response.json();
        if (error.detail && (error.detail.includes('UserNotConfirmedException') || error.detail.includes('Email not verified'))) {
          // Do not redirect automatically on login; surface message so user can choose to verify
          throw new Error('Email not verified. Please complete OTP verification.');
        }
        throw new Error(error.detail || 'Login failed');
      }
    } catch (error) {
      throw error;
    }
  };

  const signup = async (email: string, password: string, name: string, role: UserRole, phone?: string, companyName?: string) => {
    try {
      const requestBody: any = {
        name,
        email,
        password,
        role,
      };

      // Add phone for both recruiters and candidates
      requestBody.phone = phone;

      // Only add company_name for recruiters
      if (role === 'RECRUITER') {
        requestBody.company_name = companyName;
      }

      const response = await fetch('http://localhost:8000/auth/signup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        // Signup successful
        return;
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Signup failed');
      }
    } catch (error) {
      throw error;
    }
  };

  const logout = () => {
    setUser(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('aicruit_user');
      localStorage.removeItem('aicruit_tokens');
    }
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
