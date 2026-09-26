import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { getCurrentUser, loginUser, registerUser } from '../api/client.js'
import { clearStoredToken, getStoredToken, setStoredToken } from '../auth/authStorage.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getStoredToken())
  const [user, setUser] = useState(null)
  const [isRestoring, setIsRestoring] = useState(() => Boolean(getStoredToken()))

  useEffect(() => {
    const storedToken = getStoredToken()
    if (!storedToken) {
      setIsRestoring(false)
      return undefined
    }

    let isActive = true
    getCurrentUser(storedToken)
      .then((currentUser) => {
        if (!isActive) return
        setToken(storedToken)
        setUser(currentUser)
      })
      .catch(() => {
        if (!isActive) return
        clearStoredToken()
        setToken(null)
        setUser(null)
      })
      .finally(() => {
        if (isActive) setIsRestoring(false)
      })

    return () => {
      isActive = false
    }
  }, [])

  const login = useCallback(async (credentials) => {
    const tokenResponse = await loginUser(credentials)
    const currentUser = await getCurrentUser(tokenResponse.access_token)

    setStoredToken(tokenResponse.access_token)
    setToken(tokenResponse.access_token)
    setUser(currentUser)

    return currentUser
  }, [])

  const register = useCallback(async (details) => registerUser(details), [])

  const logout = useCallback(() => {
    clearStoredToken()
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(user),
      isAdmin: Boolean(user && user.role === 'admin'),
      isRestoring,
      login,
      register,
      logout,
    }),
    [user, token, isRestoring, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider.')
  }
  return context
}
