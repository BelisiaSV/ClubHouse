import { createContext, useContext, useEffect, useState } from "react";
import { getMe, getMyClub, login as apiLogin, register as apiRegister } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("access_token"));
  const [user, setUser] = useState(null);
  const [club, setClub] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadProfile = async () => {
    try {
      const [me, myClub] = await Promise.all([getMe(), getMyClub()]);
      setUser(me);
      setClub(myClub);
    } catch {
      localStorage.removeItem("access_token");
      setToken(null);
      setUser(null);
      setClub(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadProfile();
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = async (email, password) => {
    const { access_token } = await apiLogin(email, password);
    localStorage.setItem("access_token", access_token);
    setToken(access_token);
  };

  const register = async (payload) => {
    const { access_token } = await apiRegister(payload);
    localStorage.setItem("access_token", access_token);
    setToken(access_token);
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    setToken(null);
    setUser(null);
    setClub(null);
  };

  const refreshClub = async () => setClub(await getMyClub());

  return (
    <AuthContext.Provider
      value={{ token, user, club, loading, login, register, logout, refreshClub }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
