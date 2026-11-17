import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

const TOKEN_KEY = "safarismart.operator.token";

interface AuthContextValue {
  token: string | null;
  setToken: (token: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, updateToken] = useState<string | null>(() => sessionStorage.getItem(TOKEN_KEY));
  const value = useMemo<AuthContextValue>(() => ({
    token,
    setToken(nextToken) {
      sessionStorage.setItem(TOKEN_KEY, nextToken);
      updateToken(nextToken);
    },
    signOut() {
      sessionStorage.removeItem(TOKEN_KEY);
      updateToken(null);
    },
  }), [token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
