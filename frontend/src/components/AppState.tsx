"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import { useApi, type Dashboard } from "@/lib/api";
const Context = createContext<
  | (ReturnType<typeof useApi<Dashboard>> & {
      signedOut: boolean;
      setSignedOut: (value: boolean) => void;
    })
  | null
>(null);
export function AppState({ children }: { children: ReactNode }) {
  const dashboard = useApi<Dashboard>("/dashboard");
  const [signedOut, updateSignedOut] = useState(false);
  return (
    <Context.Provider
      value={{
        ...dashboard,
        signedOut,
        setSignedOut: (value: boolean) => {
          if (value) dashboard.setData(null);
          updateSignedOut(value);
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useApp() {
  const c = useContext(Context);
  if (!c) throw new Error("AppState is missing");
  return c;
}
