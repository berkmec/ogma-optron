import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

type Health = {
  status: string;
  vision_model: string;
  openai_base_url: string;
  hf_token_configured: boolean;
  agent_code_bin_set: boolean;
  agent_code_model: string;
};

type VisualAsset = {
  asset_id: string;
  filename: string;
  width: number;
  height: number;
  size_bytes: number;
};

type VisualObservation = {
  observation_id: string;
  asset_id: string;
  image_type: string;
  ocr_text: string;
  vision_description: string;
  confidence: number;
  warnings: string[];
  model_used: string;
  latency_ms: number;
};

type IntentResult = {
  intent_id: string;
  primary_intent: string;
  confidence: number;
  reasoning: string;
  ambiguity: string[];
  suggested_next_step: string;
  latency_ms: number;
};

type TaskNode = {
  task_id: string;
  task_type: string;
  description: string;
  required_agent: string;
  depends_on: string[];
};

type TaskGraph = {
  graph_id: string;
  intent_id: string;
  nodes: TaskNode[];
};

type Report = {
  report_id: string;
  title: string;
  markdown: string;
  model_used: string;
  latency_ms: number;
};

type StepName = "upload" | "analyze" | "intent" | "graph" | "report";
type Step = { name: StepName; status: "pending" | "running" | "done" | "failed"; ms?: number };

const STEPS: StepName[] = ["upload", "analyze", "intent", "graph", "report"];

const INTENT_COLORS: Record<string, string> = {
  error_debug: "#c0392b",
  repo_review: "#2c7a7b",
  ui_help: "#2c5282",
  unknown: "#6b7280",
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [userPrompt, setUserPrompt] = useState("");
  const [steps, setSteps] = useState<Step[]>(STEPS.map((n) => ({ name: n, status: "pending" })));
  const [asset, setAsset] = useState<VisualAsset | null>(null);
  const [observation, setObservation] = useState<VisualObservation | null>(null);
  const [intent, setIntent] = useState<IntentResult | null>(null);
  const [graph, setGraph] = useState<TaskGraph | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
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

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] || null;
    setFile(f);
    resetPipeline();
    setPreview(f ? URL.createObjectURL(f) : null);
  }

  function resetPipeline() {
    setAsset(null);
    setObservation(null);
    setIntent(null);
    setGraph(null);
    setReport(null);
    setError(null);
    setSteps(STEPS.map((n) => ({ name: n, status: "pending" })));
  }

  function patchStep(name: StepName, patch: Partial<Step>) {
    setSteps((prev) => prev.map((s) => (s.name === name ? { ...s, ...patch } : s)));
  }

  async function runStep<T>(name: StepName, fn: () => Promise<T>): Promise<T> {
    patchStep(name, { status: "running" });
    const t0 = performance.now();
    try {
      const result = await fn();
      patchStep(name, { status: "done", ms: Math.round(performance.now() - t0) });
      return result;
    } catch (e) {
      patchStep(name, { status: "failed", ms: Math.round(performance.now() - t0) });
      throw e;
    }
  }

  async function runPipeline() {
    if (!file) return;
    setBusy(true);
    resetPipeline();
    try {
      const uploaded = await runStep("upload", async () => {
        const fd = new FormData();
        fd.append("file", file);
        const r = await fetch("/api/assets/upload", { method: "POST", body: fd });
        if (!r.ok) throw new Error(`upload HTTP ${r.status}: ${await r.text()}`);
        return (await r.json()) as VisualAsset;
      });
      setAsset(uploaded);

      const obs = await runStep("analyze", async () => {
        const r = await fetch("/api/vision/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ asset_id: uploaded.asset_id }),
        });
        if (!r.ok) throw new Error(`analyze HTTP ${r.status}: ${await r.text()}`);
        return (await r.json()) as VisualObservation;
      });
      setObservation(obs);

      const intentRes = await runStep("intent", async () => {
        const r = await fetch("/api/intent/classify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ observation_id: obs.observation_id, user_prompt: userPrompt }),
        });
        if (!r.ok) throw new Error(`intent HTTP ${r.status}: ${await r.text()}`);
        return (await r.json()) as IntentResult;
      });
      setIntent(intentRes);

      const tg = await runStep("graph", async () => {
        const r = await fetch("/api/task-graph/build", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ intent_id: intentRes.intent_id }),
        });
        if (!r.ok) throw new Error(`graph HTTP ${r.status}: ${await r.text()}`);
        return (await r.json()) as TaskGraph;
      });
      setGraph(tg);

      const rep = await runStep("report", async () => {
        const r = await fetch("/api/reports/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ graph_id: tg.graph_id }),
        });
        if (!r.ok) throw new Error(`report HTTP ${r.status}: ${await r.text()}`);
        return (await r.json()) as Report;
      });
      setReport(rep);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      style={{
        fontFamily: "system-ui, sans-serif",
        padding: "2rem",
        maxWidth: 980,
        margin: "0 auto",
      }}
    >
      <h1>ogma-optron</h1>
      <p style={{ color: "#666" }}>
        Visual task understanding + agent routing runtime · Week 3 prototype
      </p>

      <section style={{ marginTop: "2rem" }}>
        <h2>1. Pick a screenshot, describe what you want</h2>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={onFileChange}
        />
        <textarea
          placeholder="Optional: tell me what you want from this image (e.g. 'help me debug this error')"
          value={userPrompt}
          onChange={(e) => setUserPrompt(e.target.value)}
          rows={3}
          style={{ display: "block", width: "100%", marginTop: "0.75rem", padding: "0.5rem", fontFamily: "inherit" }}
        />
        <button
          onClick={runPipeline}
          disabled={!file || busy}
          style={{ marginTop: "0.75rem", padding: "0.5rem 1rem", fontSize: "1rem" }}
        >
          {busy ? "Running pipeline..." : "Run full pipeline"}
        </button>
      </section>

      {preview && (
        <section style={{ marginTop: "1.5rem" }}>
          <img
            src={preview}
            alt="preview"
            style={{ maxWidth: "100%", maxHeight: 360, borderRadius: 4, border: "1px solid #ddd" }}
          />
        </section>
      )}

      <section style={{ marginTop: "1.5rem" }}>
        <h2>2. Pipeline progress</h2>
        <ul style={{ listStyle: "none", padding: 0, fontFamily: "ui-monospace, monospace" }}>
          {steps.map((s) => (
            <li key={s.name} style={{ display: "flex", gap: "0.75rem", padding: "0.25rem 0" }}>
              <span style={{ width: 16 }}>{stepGlyph(s.status)}</span>
              <span style={{ width: 80 }}>{s.name}</span>
              <span style={{ color: "#888" }}>{s.status}</span>
              {s.ms !== undefined && <span style={{ marginLeft: "auto", color: "#888" }}>{s.ms} ms</span>}
            </li>
          ))}
        </ul>
      </section>

      {error && (
        <pre style={{ marginTop: "1.5rem", color: "crimson", whiteSpace: "pre-wrap" }}>{error}</pre>
      )}

      {intent && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>3. Intent</h2>
          <span
            style={{
              display: "inline-block",
              padding: "0.25rem 0.75rem",
              borderRadius: 999,
              background: INTENT_COLORS[intent.primary_intent] || "#6b7280",
              color: "white",
              fontWeight: 600,
              fontFamily: "ui-monospace, monospace",
            }}
          >
            {intent.primary_intent}
          </span>
          <span style={{ marginLeft: "0.75rem", color: "#666" }}>confidence {intent.confidence.toFixed(2)}</span>
          <p style={{ marginTop: "0.5rem", color: "#333" }}>{intent.reasoning}</p>
          {intent.ambiguity.length > 0 && (
            <p style={{ color: "#a04" }}>Ambiguity: {intent.ambiguity.join("; ")}</p>
          )}
        </section>
      )}

      {graph && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>4. Task graph</h2>
          <ol style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.9rem" }}>
            {graph.nodes.map((n) => (
              <li key={n.task_id} style={{ marginBottom: "0.4rem" }}>
                <code>{n.task_type}</code> → <span style={{ color: "#555" }}>{n.required_agent}</span>
                <div style={{ color: "#888", fontSize: "0.85rem" }}>{n.description}</div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {report && (
        <section style={{ marginTop: "1.5rem" }}>
          <h2>5. {report.title}</h2>
          <small style={{ color: "#888" }}>
            {report.model_used} · {report.latency_ms} ms
          </small>
          <div
            style={{
              background: "#f4f4f4",
              padding: "1rem 1.5rem",
              borderRadius: 4,
              marginTop: "0.5rem",
            }}
          >
            <ReactMarkdown>{report.markdown}</ReactMarkdown>
          </div>
        </section>
      )}

      {observation && (
        <details style={{ marginTop: "2rem" }}>
          <summary>Observation details</summary>
          <pre
            style={{
              background: "#f4f4f4",
              padding: "1rem",
              borderRadius: 4,
              maxHeight: 320,
              overflow: "auto",
              fontSize: "0.85rem",
            }}
          >
            {JSON.stringify(observation, null, 2)}
          </pre>
        </details>
      )}

      <details style={{ marginTop: "1rem" }}>
        <summary>Backend health</summary>
        {health && (
          <pre style={{ background: "#f4f4f4", padding: "1rem", borderRadius: 4 }}>
            {JSON.stringify(health, null, 2)}
          </pre>
        )}
      </details>
    </main>
  );
}

function stepGlyph(status: Step["status"]): string {
  switch (status) {
    case "pending":
      return "·";
    case "running":
      return "→";
    case "done":
      return "✓";
    case "failed":
      return "✗";
  }
}
