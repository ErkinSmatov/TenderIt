import { jwtVerify } from 'jose'
import { NextRequest, NextResponse } from 'next/server'

const SECRET = new TextEncoder().encode(process.env.JWT_SECRET!)
const protectedRoutes = ['/dashboard', '/profile', '/tenders', '/applications', '/documents']

export async function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname
  const isProtected = protectedRoutes.some(r => path.startsWith(r))

  if (!isProtected) return NextResponse.next()

  const token = req.cookies.get('access_token')?.value
  if (!token) return NextResponse.redirect(new URL('/login', req.url))

  try {
    await jwtVerify(token, SECRET)
    return NextResponse.next()
  } catch {
    // Token expired or invalid — redirect to login; client-side will attempt silent refresh
    return NextResponse.redirect(new URL('/login', req.url))
  }
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
