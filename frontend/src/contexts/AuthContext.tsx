import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, ApiError } from '../lib/api-client';
import type { UserBrief } from '../types';

interface AuthState {
  user: UserBrief | null;
  loading: boolean;
  isLoggedIn: boolean;
  refetch: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  isLoggedIn: false,
  refetch: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserBrief | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = async () => {
    try {
      const u = await api.get<UserBrief>('/users/me');
      setUser(u);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isLoggedIn: !!user,
        refetch: fetchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
