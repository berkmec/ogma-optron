import { useEffect, useState } from "react";

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
  mime_type: string;
  width: number;
  height: number;
  size_bytes: number;
  storage_path: string;
  created_at: string;
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
  created_at: string;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [asset, setAsset] = useState<VisualAsset | null>(null);
  const [observation, setObservation] = useState<VisualObservation | null>(null);
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
    setAsset(null);
    setObservation(null);
    setError(null);
    setPreview(f ? URL.createObjectURL(f) : null);
  }

  async function uploadAndAnalyze() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setObservation(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const upR = await fetch("/api/assets/upload", { method: "POST", body: fd });
      if (!upR.ok) throw new Error(`upload HTTP ${upR.status}: ${await upR.text()}`);
      const upJ: VisualAsset = await upR.json();
      setAsset(upJ);

      const anR = await fetch("/api/vision/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_id: upJ.asset_id }),
      });
      if (!anR.ok) throw new Error(`analyze HTTP ${anR.status}: ${await anR.text()}`);
      setObservation(await anR.json());
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
        maxWidth: 900,
        margin: "0 auto",
      }}
    >
      <h1>ogma-optron</h1>
      <p style={{ color: "#666" }}>
        Visual task understanding runtime · Week 2 prototype
      </p>

      <section style={{ marginTop: "2rem" }}>
        <h2>Upload a screenshot</h2>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={onFileChange}
        />
        <button
          onClick={uploadAndAnalyze}
          disabled={!file || busy}
          style={{ marginLeft: "1rem", padding: "0.5rem 1rem" }}
        >
          {busy ? "Analyzing..." : "Upload + Analyze"}
        </button>
      </section>

      {preview && (
        <section style={{ marginTop: "1.5rem" }}>
          <img
            src={preview}
            alt="preview"
            style={{
              maxWidth: "100%",
              maxHeight: 400,
              borderRadius: 4,
              border: "1px solid #ddd",
            }}
          />
        </section>
      )}

      {error && (
        <pre style={{ marginTop: "1.5rem", color: "crimson", whiteSpace: "pre-wrap" }}>
          {error}
        </pre>
      )}

      {asset && (
        <section style={{ marginTop: "1.5rem" }}>
          <h3>Asset</h3>
          <small>
            {asset.filename} · {asset.width}×{asset.height} ·{" "}
            {(asset.size_bytes / 1024).toFixed(1)} KB · id{" "}
            {asset.asset_id.slice(0, 8)}…
          </small>
        </section>
      )}

      {observation && (
        <section style={{ marginTop: "1.5rem" }}>
          <h3>Observation</h3>
          <div
            style={{
              display: "grid",
              gap: "0.5rem 1rem",
              gridTemplateColumns: "max-content 1fr",
              alignItems: "baseline",
            }}
          >
            <strong>image_type</strong>
            <code>{observation.image_type}</code>
            <strong>model</strong>
            <code>{observation.model_used}</code>
            <strong>latency</strong>
            <span>{observation.latency_ms} ms</span>
            <strong>confidence</strong>
            <span>{observation.confidence}</span>
          </div>
          {observation.warnings.length > 0 && (
            <p style={{ color: "#a04" }}>
              Warnings: {observation.warnings.join(", ")}
            </p>
          )}
          <h4>OCR text</h4>
          <pre
            style={{
              background: "#f4f4f4",
              padding: "1rem",
              borderRadius: 4,
              maxHeight: 240,
              overflow: "auto",
            }}
          >
            {observation.ocr_text || "(no text detected)"}
          </pre>
          <h4>Vision description</h4>
          <p style={{ background: "#f4f4f4", padding: "1rem", borderRadius: 4 }}>
            {observation.vision_description || "(empty)"}
          </p>
        </section>
      )}

      <details style={{ marginTop: "2rem" }}>
        <summary>Backend health</summary>
        {health && (
          <pre
            style={{ background: "#f4f4f4", padding: "1rem", borderRadius: 4 }}
          >
            {JSON.stringify(health, null, 2)}
          </pre>
        )}
      </details>
    </main>
  );
}
