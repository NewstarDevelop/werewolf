/* eslint-disable react-refresh/only-export-components */
/**
 * Authentication context for global user state management.
 */
import React, { createContext, useContext, useState, useEffect, useRef, ReactNode, useCallback, useMemo } from 'react';
import { authService, User, AuthError } from '@/services/authService';
import { clearUserToken } from '@/utils/token';
import { clearPlayerData } from '@/utils/player';
import { useToast } from '@/hooks/use-toast';
import { useTranslation } from 'react-i18next';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, nickname: string) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (updates: Partial<User>) => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();
  const toastRef = useRef(toast);
  toastRef.current = toast;
  const { t } = useTranslation();
  const tRef = useRef(t);
  tRef.current = t;

  useEffect(() => {
    const initAuth = async () => {
      try {
        const currentUser = await authService.getCurrentUser();
        setUser(currentUser);
      } catch (error: unknown) {
        const status = error instanceof AuthError ? error.status : 0;

        // 分类处理错误
        if (status === 401 || status === 403) {
          // Token 过期/无效: 静默失败，清理状态，用户需重新登录
          clearUserToken();
          setUser(null);
        } else if (status >= 500) {
          // 服务器错误：提示用户
          console.error('Server error during auth:', error);
          toastRef.current({
            variant: "destructive",
            title: tRef.current("auth.server_error"),
            description: tRef.current("auth.server_error_desc"),
          });
          setUser(null);
        } else {
          // 网络断开等其他错误
          console.warn('Network/Auth init error:', error);
        }
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await authService.login(email, password);
    setUser(response.user);
  }, []);

  const register = useCallback(async (email: string, password: string, nickname: string) => {
    const response = await authService.register(email, password, nickname);
    setUser(response.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch (error) {
      console.error('Logout API call failed:', error);
      // Continue with local cleanup even if server request fails
    } finally {
      // Always clear local state regardless of server response
      clearPlayerData(); // 清除所有本地数据（player_id, nickname, tokens）
      clearUserToken();
      setUser(null);
    }
  }, []);

  const updateUser = useCallback((updates: Partial<User>) => {
    setUser((prev) => (prev ? { ...prev, ...updates } : null));
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      console.error('Failed to refresh user:', error);
      throw error;
    }
  }, []);

  const value = useMemo<AuthContextType>(() => ({
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    updateUser,
    refreshUser,
  }), [user, isLoading, login, register, logout, updateUser, refreshUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
