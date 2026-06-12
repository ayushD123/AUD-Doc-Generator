"use client";

import { useState } from "react";

type HealthState = "idle" | "checking" | "ok" | "error";

type HealthResponse = {
  status: string;
  service: string;
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

export default function Home() {
  const [healthState, setHealthState] = useState<HealthState>("idle");
  const [message, setMessage] = useState("Backend health has not been checked yet.");

  async function checkBackendHealth() {
    if (!apiBaseUrl) {
      setHealthState("error");
      setMessage("NEXT_PUBLIC_API_BASE_URL is not configured.");
      return;
    }

    setHealthState("checking");
    setMessage("Checking backend health...");

    try {
      const response = await fetch(`${apiBaseUrl}/health`, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}.`);
      }

      const data = (await response.json()) as HealthResponse;

      if (data.status !== "ok") {
        throw new Error("Backend health response did not report status ok.");
      }

      setHealthState("ok");
      setMessage(`status ok from ${data.service}`);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setHealthState("error");
      setMessage(`Backend unavailable: ${detail}`);
    }
  }

  return (
    <main className="page-shell">
      <section className="workspace-panel" aria-labelledby="app-title">
        <div className="intro">
          <h1 id="app-title">AUD Generator</h1>
          <p className="subtitle">Internal Oracle AUD generation workspace</p>
        </div>

        <div className="health-card" aria-live="polite">
          <div>
            <h2>Backend health status</h2>
            <p className={`status-message status-${healthState}`}>{message}</p>
          </div>

          <button
            type="button"
            className="health-button"
            onClick={checkBackendHealth}
            disabled={healthState === "checking"}
          >
            {healthState === "checking" ? "Checking..." : "Check Backend Health"}
          </button>
        </div>
      </section>
    </main>
  );
}
