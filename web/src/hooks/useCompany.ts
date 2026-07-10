"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, Tenant } from "@/lib/api";
import { getToken } from "@/lib/auth";

export function useCompany() {
  const [company, setCompany] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    setLoading(true);
    try {
      setCompany(await api.getCompany(token));
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load company");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { company, loading, error, reload: load, setCompany };
}
