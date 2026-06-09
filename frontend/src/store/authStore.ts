import { create } from 'zustand'

interface AuthState {
  isAuthenticated: boolean
  userId: number | null
  setAuth: (userId: number) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  userId: null,
  setAuth: (userId) => set({ isAuthenticated: true, userId }),
  clearAuth: () => set({ isAuthenticated: false, userId: null }),
}))
