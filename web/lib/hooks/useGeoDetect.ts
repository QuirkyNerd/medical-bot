"use client";

import { useEffect, useRef } from "react";
import type { SupportedLanguage } from "../i18n";
import { apiRequest } from "../api-client";

export type GeoResult = {
  country: string;
  language: SupportedLanguage;
  emergencyNumber: string;
  source: "header" | "ipapi" | "default";
};

type Options = {
  skip: boolean;
  onResult: (result: GeoResult) => void;
};

export function useGeoDetect({ skip, onResult }: Options): void {
  const fired = useRef(false);

  useEffect(() => {
    if (skip || fired.current) return;
    fired.current = true;

    apiRequest("/api/geo")
      .then((data: GeoResult) => {
        if (data && data.country) onResult(data);
      })
      .catch(() => {
        /* silent fallback */
      });

  }, [skip, onResult]);
}
