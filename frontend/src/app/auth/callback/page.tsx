'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function AuthCallback() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = searchParams.get('token');

    if (token) {
      // Store the JWT token in localStorage
      localStorage.setItem('auth_token', token);

      // Redirect to home page or dashboard
      router.push('/');
    } else {
      // No token found, redirect to login or show error
      console.error('No token received from authentication');
      router.push('/');
    }
  }, [searchParams, router]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-4">Authenticating...</h1>
        <p className="text-black">Please wait while we log you in.</p>
      </div>
    </div>
  );
}
