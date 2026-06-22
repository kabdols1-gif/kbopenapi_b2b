"use client";

import { useEffect, useMemo, useState } from "react";
import kbCatalog from "./samples.generated.json";
import OpenApiTestClient, {
  type OpenApiSample,
  type OpenApiTokenProcedure,
} from "@/components/openapi/OpenApiTestClient";

const FALLBACK_BASE_URL =
  process.env.NEXT_PUBLIC_OPENAPI_TEST_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8020";

const BUILD_RUNTIME_MODE = normalizeRuntimeMode(process.env.NEXT_PUBLIC_OPENAPI_MODE);

type ApiMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type RuntimeMode = "development" | "production";

type CatalogSample = {
  id: string;
  label: string;
  method: ApiMethod;
  endpoint?: string;
  path?: string;
  transactionCode?: string;
  description: string;
  headers?: Record<string, string>;
  query?: Record<string, unknown>;
  body?: Record<string, unknown>;
};

type KbCatalog = {
  b2b?: CatalogSample[];
};

type RuntimeEnvironmentConfig = {
  kbB2bBaseUrl?: string;
};

type RuntimeConfig = {
  mode?: string;
  environment?: RuntimeEnvironmentConfig;
  environments?: Partial<Record<RuntimeMode, RuntimeEnvironmentConfig>>;
};

const DEFAULT_ENVIRONMENTS: Record<RuntimeMode, Required<RuntimeEnvironmentConfig>> = {
  development: {
    kbB2bBaseUrl: process.env.NEXT_PUBLIC_OPENAPI_DEV_KB_B2B_BASE_URL || "https://dbaasapi.kbsec.com:32484",
  },
  production: {
    kbB2bBaseUrl: process.env.NEXT_PUBLIC_OPENAPI_PROD_KB_B2B_BASE_URL || "https://baasapi.kbsec.com:32484",
  },
};

function normalizeRuntimeMode(raw: string | undefined | null): RuntimeMode {
  const normalized = (raw || "").trim().toLowerCase();
  return ["prod", "production", "real", "live"].includes(normalized) ? "production" : "development";
}

function environmentForMode(config: RuntimeConfig | null, mode: RuntimeMode): Required<RuntimeEnvironmentConfig> {
  const defaults = DEFAULT_ENVIRONMENTS[mode];
  const fromMode = config?.environments?.[mode] ?? {};
  const active = normalizeRuntimeMode(config?.mode) === mode ? config?.environment ?? {} : {};
  return {
    kbB2bBaseUrl: active.kbB2bBaseUrl || fromMode.kbB2bBaseUrl || defaults.kbB2bBaseUrl || FALLBACK_BASE_URL,
  };
}

function toKbServicePath(entry: CatalogSample) {
  if (entry.path) return entry.path;
  if (entry.endpoint?.startsWith("/baas/")) return entry.endpoint;

  const transactionCode = (entry.transactionCode || entry.id)
    .replace(/^Tkb_/i, "")
    .replace(/_B2B(?:__\d+)?$/i, "")
    .toLowerCase();
  return `/baas/v2/${transactionCode}`;
}

function toOpenApiSample(entry: CatalogSample, baseUrl: string): OpenApiSample {
  return {
    id: entry.id,
    label: entry.label.replace(/\.xml$/i, ""),
    method: entry.method,
    path: toKbServicePath(entry),
    description: entry.description,
    headers: {
      "Content-Type": "application/json",
      Authorization: "bearer {{access_token}}",
      ...(entry.headers ?? {}),
    },
    query: entry.query,
    body: entry.body,
    baseUrl,
    source: "trx-rule",
  };
}

function tokenProcedureForMode(mode: RuntimeMode, baseUrl: string): OpenApiTokenProcedure {
  return {
    id: "kb-b2b-token",
    label: "KB B2B 토큰 발급",
    mode: "B2B",
    environment: baseUrl || DEFAULT_ENVIRONMENTS[mode].kbB2bBaseUrl,
    steps: [
      `1) POST ${baseUrl}/baas/v2/clause_agree_process 로 이용약관 동의를 등록합니다.`,
      `2) POST ${baseUrl}/baas/v2/email_agree_process 로 금융거래 동의를 등록합니다.`,
      `3) POST ${baseUrl}/baas/v2/baas_auth_issue 로 code와 issueNo를 발급합니다.`,
      `4) POST ${baseUrl}/baas/v2/baas_token_issue 에 code, issueNo, clientId/clientSecret, grantType=authorization_code, scope=public security를 전달합니다.`,
      "5) 응답의 access_token을 샘플 API 요청 Authorization 헤더에 사용합니다.",
    ],
    recommendedHeaders: [
      "Authorization: bearer <access_token>",
      "Content-Type: application/json",
    ],
  };
}

export default function OpenApiTestPage() {
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | null>(null);
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode>(() => {
    if (typeof window === "undefined" || BUILD_RUNTIME_MODE === "production") return BUILD_RUNTIME_MODE;
    try {
      const cached = window.localStorage.getItem("kb.openapi.b2b.runtimeMode");
      return cached ? normalizeRuntimeMode(cached) : BUILD_RUNTIME_MODE;
    } catch {
      return BUILD_RUNTIME_MODE;
    }
  });

  useEffect(() => {
    let isCancelled = false;
    fetch("/api/config/runtime")
      .then((response) => (response.ok ? response.json() : null))
      .then((config) => {
        if (!isCancelled && config && typeof config === "object") {
          setRuntimeConfig(config as RuntimeConfig);
        }
      })
      .catch(() => {
        if (!isCancelled) setRuntimeConfig(null);
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  function selectRuntimeMode(mode: RuntimeMode) {
    setRuntimeMode(mode);
    try {
      window.localStorage.setItem("kb.openapi.b2b.runtimeMode", mode);
    } catch {
      // Runtime mode persistence is optional.
    }
  }

  const activeEnvironment = useMemo(
    () => environmentForMode(runtimeConfig, runtimeMode),
    [runtimeConfig, runtimeMode],
  );
  const defaultBaseUrl = activeEnvironment.kbB2bBaseUrl || FALLBACK_BASE_URL;
  const samples = useMemo(
    () => ((kbCatalog as KbCatalog).b2b ?? []).map((entry) => toOpenApiSample(entry, defaultBaseUrl)),
    [defaultBaseUrl],
  );
  const tokenProcedures = useMemo(
    () => [tokenProcedureForMode(runtimeMode, defaultBaseUrl)],
    [defaultBaseUrl, runtimeMode],
  );

  return (
    <OpenApiTestClient
      headerContent={
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-4 border-[#fcb514] pb-4">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-[#fcb514] text-lg font-black text-[#2c2a26]">
              KB
            </div>
            <div className="min-w-0">
              <p className="text-sm font-black text-[#8a6400]">KB OpenAPI</p>
              <h1 className="text-2xl font-black tracking-normal text-[#2c2a26]">KB B2B OpenAPI 테스트</h1>
              <p className="mt-1 text-sm font-semibold text-slate-500">KB증권 B2B API 연동 테스트</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs font-black">
            <span className="rounded-full bg-[#fff4cc] px-3 py-1 text-[#7a5500]">B2B {samples.length}건</span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">{runtimeMode}</span>
          </div>
        </div>
      }
      modeSelectorContent={
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[#e3d8bd] bg-[#fffaf0] px-3 py-2">
          <span className="text-xs font-black text-[#6b5b3f]">환경</span>
          {(["development", "production"] as RuntimeMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => selectRuntimeMode(mode)}
              className={`rounded-md border px-3 py-1.5 text-xs font-black transition ${
                runtimeMode === mode
                  ? "border-[#2c2a26] bg-[#2c2a26] text-white"
                  : "border-[#d7cfbf] bg-white text-[#2c2a26] hover:bg-[#fff4cc]"
              }`}
            >
              {mode === "production" ? "운영" : "개발"}
            </button>
          ))}
        </div>
      }
      runtimeMode={runtimeMode}
      samples={samples}
      historyStorageKey="kb.openapi.b2b.sample.history"
      defaultBaseUrl={defaultBaseUrl}
      broker="Tkb"
      credentialStorageKey="kb.openapi.b2b.sample.credentials"
      tokenProcedures={tokenProcedures}
    />
  );
}
