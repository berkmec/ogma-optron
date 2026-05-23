import { useEffect, useState } from "react";

type Health = {
  status: string;
  vision_model: string;
  openai_base_url: string;
  hf_token_configured: boolean;
  agent_code_bin_set: boolean;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 720 }}>
      <h1>ogma-optron</h1>
      <p style={{ color: "#666" }}>
        Visual task understanding and agent routing runtime. Week 1 skeleton.
      </p>
      <section>
        <h2>Backend health</h2>
        {error && <pre style={{ color: "crimson" }}>Error: {error}</pre>}
        {!error && !health && <p>Loading...</p>}
        {health && (
          <pre style={{ background: "#f4f4f4", padding: "1rem", borderRadius: 4 }}>
            {JSON.stringify(health, null, 2)}
          </pre>
        )}
      </section>
    </main>
  );
}
