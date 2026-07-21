// Data-fetching hook with the loading / error / reload triad every consumed
// endpoint gets (docs/stack-frontend.md: a view that only renders the happy path
// is not done). A 401 is re-thrown as a signal so the app can send Tyler to login.
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./client";

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | Error | null;
  loading: boolean;
  reload: () => void;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  onUnauthorized?: () => void,
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (!live) return;
        setData(result);
      })
      .catch((err: unknown) => {
        if (!live) return;
        if (err instanceof ApiError && err.status === 401) {
          onUnauthorized?.();
        }
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
    // fetcher is expected to be stable or memoized by the caller.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce]);

  return { data, error, loading, reload };
}
