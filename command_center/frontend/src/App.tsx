// Session gate for the single-user surface (Tyler only). We ask /api/me; a 401
// means no valid session, so we show a login screen that links to the backend's
// Google OIDC flow (/api/auth/login). No token or secret is ever handled here —
// auth is entirely the signed session cookie the backend owns.
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api/client";
import type { UserOut } from "./api/types";
import { ToastProvider } from "./components/ToastProvider";
import { Shell } from "./components/Shell";

type SessionState =
  | { status: "loading" }
  | { status: "authed"; user: UserOut }
  | { status: "anon" }
  | { status: "error"; message: string };

export function App() {
  const [session, setSession] = useState<SessionState>({ status: "loading" });

  const load = useCallback(() => {
    setSession({ status: "loading" });
    api
      .me()
      .then((user) => setSession({ status: "authed", user }))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setSession({ status: "anon" });
        } else {
          setSession({
            status: "error",
            message: err instanceof Error ? err.message : "Sign-in check failed",
          });
        }
      });
  }, []);

  useEffect(load, [load]);

  if (session.status === "loading") {
    return (
      <div className="login-screen">
        <div className="login-card">
          <span className="spin" aria-hidden="true" />
          <p>Checking your session…</p>
        </div>
      </div>
    );
  }

  if (session.status === "authed") {
    return (
      <ToastProvider>
        <Shell user={session.user} />
      </ToastProvider>
    );
  }

  // anon or error: both route to the same sign-in affordance.
  return (
    <div className="login-screen">
      <div className="login-card">
        <h1>emctl · command center</h1>
        <p>
          {session.status === "error"
            ? session.message
            : "A single-user surface — Tyler only. Sign in with the household Google account to reach the line."}
        </p>
        {/* Full-page navigation: OIDC is a redirect flow the backend drives. */}
        <a className="btn btn-gate" href="/api/auth/login">
          Sign in with Google
        </a>
        {session.status === "error" && (
          <button className="btn btn-ghost btn-sm" onClick={load}>
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
