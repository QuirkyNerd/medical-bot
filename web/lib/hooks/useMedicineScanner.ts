"use client";

import { useState, useCallback } from "react";
import type { MedicineItem, MedicineForm } from "@/lib/health-store";
import { apiRequest } from "../api-client";

interface ScanResult {
  success: boolean;
  medicine?: Omit<MedicineItem, "id" | "createdAt">;
  error?: string;
  model_used?: string;
}

type ScannerStatus = "idle" | "waking" | "scanning";

export function useMedicineScanner() {
  const [status, setStatus] = useState<ScannerStatus>("idle");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isAwake = useCallback(async (): Promise<boolean> => {
    try {
      const data = await apiRequest("/api/scan/health");
      return data.status === "ok";
    } catch {
      return false;
    }
  }, []);

  const wakeSpace = useCallback(async (): Promise<boolean> => {
    if (await isAwake()) return true;

    setStatus("waking");
    const maxAttempts = 36; // 3 min
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 5000));
      if (await isAwake()) return true;
    }
    return false;
  }, [isAwake]);

  const scan = useCallback(async (imageFile: File | Blob) => {
    setStatus("waking");
    setResult(null);
    setError(null);

    try {
      const awake = await wakeSpace();
      if (!awake) {
        setError("Scanner is starting up. Please try again in a moment.");
        setResult({ success: false, error: "Scanner Space is still waking up." });
        setStatus("idle");
        return;
      }

      setStatus("scanning");
      const formData = new FormData();
      formData.append("image", imageFile);

      const data = await apiRequest("/api/scan", {
        method: "POST",
        body: formData
      });

      if (data.success && data.medicine) {
        const validForms: MedicineForm[] = [
          "tablet", "capsule", "syrup", "inhaler",
          "injection", "cream", "drops", "patch", "other",
        ];
        if (!validForms.includes(data.medicine.form)) {
          data.medicine.form = "other";
        }
        if (typeof data.medicine.quantity !== "number" || data.medicine.quantity < 1) {
          data.medicine.quantity = 1;
        }
        setResult(data);
      } else {
        setError(data.error || "Scan failed");
        setResult(data);
      }
    } catch (e: any) {
      const msg = e?.message || "Network error — scanner unavailable";
      setError(msg);
      setResult({ success: false, error: msg });
    } finally {
      setStatus("idle");
    }
  }, [wakeSpace]);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return {
    scan,
    scanning: status !== "idle",
    waking: status === "waking",
    status,
    result,
    error,
    reset,
  };
}
