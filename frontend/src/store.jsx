import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return null;
    }
    try {
      const me = await api.me();
      setUser(me);
      return me;
    } catch {
      setToken("");
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const signIn = async (credentials) => {
    const data = await api.login(credentials);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  };

  const signUp = async (payload) => {
    const data = await api.register(payload);
    setToken(data.token);
    setUser(data.user);
    return data; // includes demo_code + needs_verification
  };

  const signOut = async () => {
    try {
      await api.logout();
    } catch {
      /* token already gone */
    }
    setToken("");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
