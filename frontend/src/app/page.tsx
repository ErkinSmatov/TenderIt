import { redirect } from 'next/navigation'

/**
 * Root page — redirects to /dashboard.
 * Middleware handles auth: unauthenticated users are redirected to /login.
 */
export default function RootPage() {
  redirect('/dashboard')
}
