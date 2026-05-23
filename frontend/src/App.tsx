import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/utils/cn";

type ImageType = string;

type VisualObservation = {
  observation_id: string;
  asset_id: string;
  image_type: ImageType;
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

type AgentTrace = {
  task_id: string;
  task_type: string;
  agent_name: string;
  status: "pending" | "running" | "done" | "failed" | "skipped";
  output_summary: string;
  detail_markdown: string;
  warnings: string[];
  model_used: string;
  latency_ms: number;
  error: string;
};

type AgentRun = {
  run_id: string;
  status: "pending" | "running" | "done" | "failed" | "partial";
  traces: AgentTrace[];
  total_latency_ms: number;
  failed_count: number;
  skipped_count: number;
};

type Turn = {
  id: string;
  role: "user" | "assistant" | "error" | "system";
  content: string;
  image?: string;
  pipeline?: {
    observation: VisualObservation;
    intent: IntentResult;
    graph: TaskGraph;
    run: AgentRun;
  };
  timestamp: Date;
};

const SUGGESTIONS = [
  "Bir hata ekran görüntüsü yükle",
  "Bir GitHub repo screenshot'ı analiz et",
  "Bir UI tasarımı incelet",
];

const STATUS_STYLES: Record<AgentTrace["status"], string> = {
  pending:  "bg-white/5 text-gray-400",
  running:  "bg-blue-500/20 text-blue-300",
  done:     "bg-emerald-500/15 text-emerald-300",
  failed:   "bg-red-500/20 text-red-300",
  skipped:  "bg-amber-500/15 text-amber-300",
};

const INTENT_BG: Record<string, string> = {
  error_debug: "bg-red-500/15 text-red-300 border-red-500/30",
  repo_review: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  ui_help:     "bg-sky-500/15 text-sky-300 border-sky-500/30",
  unknown:     "bg-gray-500/15 text-gray-300 border-gray-500/30",
};

function uid() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function formatTime(d: Date) {
  return d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

function lastObservationId(turns: Turn[]): string | null {
  for (let i = turns.length - 1; i >= 0; i--) {
    const obs = turns[i].pipeline?.observation;
    if (obs) return obs.observation_id;
  }
  return null;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} HTTP ${r.status}: ${await r.text()}`);
  return (await r.json()) as T;
}

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [selected, setSelected] = useState<{ dataUrl: string; file: File } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, isLoading]);

  function pickFile(file: File) {
    const reader = new FileReader();
    reader.onloadend = () => {
      setSelected({ dataUrl: reader.result as string, file });
    };
    reader.readAsDataURL(file);
  }

  function clearSelected() {
    setSelected(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function pushTurn(t: Omit<Turn, "id" | "timestamp"> & { id?: string }) {
    setTurns((prev) => [
      ...prev,
      { id: t.id ?? uid(), timestamp: new Date(), ...t } as Turn,
    ]);
  }

  async function runVisionTurn(file: File, dataUrl: string, prompt: string) {
    pushTurn({ role: "user", content: prompt, image: dataUrl });
    setIsLoading(true);
    try {
      setLoadingStep("Görsel yükleniyor…");
      const fd = new FormData();
      fd.append("file", file);
      const upR = await fetch("/api/assets/upload", { method: "POST", body: fd });
      if (!upR.ok) throw new Error(`upload HTTP ${upR.status}: ${await upR.text()}`);
      const asset = (await upR.json()) as { asset_id: string };

      setLoadingStep("Görsel analiz ediliyor…");
      const observation = await postJson<VisualObservation>("/api/vision/analyze", {
        asset_id: asset.asset_id,
      });

      setLoadingStep("Niyet çıkarılıyor…");
      const intent = await postJson<IntentResult>("/api/intent/classify", {
        observation_id: observation.observation_id,
        user_prompt: prompt,
      });

      setLoadingStep("Görev planı hazırlanıyor…");
      const graph = await postJson<TaskGraph>("/api/task-graph/build", {
        intent_id: intent.intent_id,
      });

      setLoadingStep("Agent'lar çalışıyor…");
      const run = await postJson<AgentRun>("/api/agents/run", {
        graph_id: graph.graph_id,
      });

      const reportTrace = run.traces.find((t) => t.task_type === "draft_report");
      const content = reportTrace?.detail_markdown?.trim() || "_(rapor üretilemedi)_";
      pushTurn({
        role: "assistant",
        content,
        pipeline: { observation, intent, graph, run },
      });
    } catch (e) {
      pushTurn({ role: "error", content: String(e) });
    } finally {
      setIsLoading(false);
      setLoadingStep("");
    }
  }

  async function runChatTurn(question: string, observationId: string) {
    pushTurn({ role: "user", content: question });
    setIsLoading(true);
    setLoadingStep("Düşünüyor…");
    try {
      const data = await postJson<{
        user_message: { message_id: string };
        assistant_message: { message_id: string; content: string };
      }>("/api/chat", {
        observation_id: observationId,
        question,
      });
      pushTurn({
        id: data.assistant_message.message_id,
        role: "assistant",
        content: data.assistant_message.content,
      });
    } catch (e) {
      pushTurn({ role: "error", content: String(e) });
    } finally {
      setIsLoading(false);
      setLoadingStep("");
    }
  }

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (isLoading) return;
    const text = input.trim();
    if (!selected && !text) return;
    setInput("");

    if (selected) {
      const sel = selected;
      setSelected(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await runVisionTurn(sel.file, sel.dataUrl, text);
      return;
    }
    const obsId = lastObservationId(turns);
    if (!obsId) {
      pushTurn({
        role: "system",
        content:
          "Önce bir görsel yükleyin — takip soruları yüklediğiniz görselin context'ine bağlanır.",
      });
      return;
    }
    await runChatTurn(text, obsId);
  }

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <header className="border-b border-white/10 bg-black/95 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-lg font-medium tracking-wide">Ogma Optron</h1>
          <span className="text-xs text-gray-500 hidden sm:inline">
            Qwen3-VL · agent runtime
          </span>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          {turns.length === 0 ? (
            <EmptyState
              onPick={(s) => setInput(s)}
              onUpload={() => fileInputRef.current?.click()}
            />
          ) : (
            <div className="space-y-6">
              {turns.map((t) => (
                <TurnView key={t.id} turn={t} />
              ))}
              {isLoading && <LoadingBubble label={loadingStep} />}
              <div ref={endRef} />
            </div>
          )}
        </div>
      </main>

      <footer className="border-t border-white/10 bg-black/95 sticky bottom-0">
        <div className="max-w-4xl mx-auto px-4 py-4">
          {selected && (
            <div className="mb-3 relative inline-block">
              <img
                src={selected.dataUrl}
                alt="seçili"
                className="h-20 w-20 object-cover rounded-lg border border-white/10"
              />
              <button
                type="button"
                onClick={clearSelected}
                className="absolute -top-2 -right-2 w-6 h-6 bg-white rounded-full flex items-center justify-center text-black hover:bg-gray-200 transition-colors"
                aria-label="Görseli kaldır"
              >
                <CloseIcon />
              </button>
            </div>
          )}
          <form onSubmit={handleSubmit} className="flex items-end gap-3">
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) pickFile(f);
              }}
              accept="image/png,image/jpeg,image/webp,image/gif"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              className="flex-shrink-0 w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-gray-500 hover:text-white hover:bg-white/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              title="Görsel yükle"
            >
              <ImageIcon />
            </button>
            <div className="flex-1">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                placeholder={
                  selected
                    ? "Görsel hakkında ne sormak istersiniz? (opsiyonel)"
                    : turns.some((t) => t.pipeline)
                    ? "Takip sorusu yazın veya yeni bir görsel yükleyin…"
                    : "Önce bir görsel yükleyin, sonra prompt yazın…"
                }
                rows={1}
                className="w-full resize-none rounded-xl bg-white/5 border border-white/10 px-5 py-3.5 text-white placeholder-gray-600 focus:outline-none focus:border-white/30 transition-all"
                style={{ maxHeight: "150px" }}
                disabled={isLoading}
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || (!selected && !input.trim())}
              className="flex-shrink-0 w-12 h-12 rounded-xl bg-white text-black flex items-center justify-center hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              title="Gönder (Enter)"
            >
              <SendIcon />
            </button>
          </form>
          <p className="text-center text-xs text-gray-700 mt-3">
            Vision → intent → task graph → agents → markdown. Mesajın altındaki "Pipeline details" ile akışı görebilirsiniz.
          </p>
        </div>
      </footer>
    </div>
  );
}

function EmptyState({
  onPick,
  onUpload,
}: {
  onPick: (text: string) => void;
  onUpload: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center">
      <h2 className="text-2xl font-light mb-2">Ogma Optron</h2>
      <p className="text-gray-500 max-w-md text-sm">
        Bir ekran görüntüsü yükleyin — sistem niyetinizi tanır, bir görev planı çıkarır, agent'larını çalıştırır ve markdown raporu döndürür.
      </p>
      <button
        onClick={onUpload}
        className="mt-6 px-5 py-2.5 rounded-xl bg-white text-black text-sm font-medium hover:bg-gray-200 transition-colors"
      >
        Görsel yükle
      </button>
      <div className="flex flex-wrap gap-3 mt-8 justify-center">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-gray-400 text-sm hover:bg-white/10 hover:text-white transition-all"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl px-5 py-4 bg-white text-black">
          {turn.image && (
            <img
              src={turn.image}
              alt="yüklenen"
              className="mb-3 max-w-full max-h-64 rounded-lg object-contain bg-white/30"
            />
          )}
          {turn.content && (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{turn.content}</p>
          )}
          <p className="text-xs mt-2 text-gray-500">{formatTime(turn.timestamp)}</p>
        </div>
      </div>
    );
  }

  if (turn.role === "error") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl px-5 py-4 bg-red-500/10 border border-red-500/30 text-red-200">
          <p className="text-xs text-red-300 mb-1">Hata</p>
          <p className="text-sm leading-relaxed whitespace-pre-wrap font-mono">{turn.content}</p>
        </div>
      </div>
    );
  }

  if (turn.role === "system") {
    return (
      <div className="flex justify-center">
        <div className="rounded-full px-4 py-2 bg-white/5 border border-white/10 text-gray-400 text-xs">
          {turn.content}
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl px-5 py-4 bg-white/5 border border-white/10 text-white">
        <div className="prose prose-invert prose-sm max-w-none text-sm leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.content}</ReactMarkdown>
        </div>
        {turn.pipeline && <PipelineDetails pipeline={turn.pipeline} />}
        <p className="text-xs mt-2 text-gray-600">
          {formatTime(turn.timestamp)}
          {turn.pipeline && (
            <span className="ml-2">· {turn.pipeline.run.total_latency_ms} ms · {turn.pipeline.run.traces.length} agents</span>
          )}
        </p>
      </div>
    </div>
  );
}

function PipelineDetails({ pipeline }: { pipeline: NonNullable<Turn["pipeline"]> }) {
  const { observation, intent, graph, run } = pipeline;
  return (
    <details className="mt-3 text-xs group">
      <summary className="cursor-pointer text-gray-500 hover:text-gray-300 select-none">
        Pipeline details
      </summary>
      <div className="mt-3 space-y-3 border-l border-white/10 pl-3">
        <div className="flex flex-wrap gap-3 items-center">
          <span
            className={cn(
              "px-2 py-0.5 rounded border text-[11px] font-mono",
              INTENT_BG[intent.primary_intent] || INTENT_BG.unknown,
            )}
          >
            {intent.primary_intent}
          </span>
          <span className="text-gray-500">
            image_type: <code className="text-gray-300">{observation.image_type}</code>
          </span>
          <span className="text-gray-500">
            confidence: <code className="text-gray-300">{intent.confidence.toFixed(2)}</code>
          </span>
        </div>

        {intent.reasoning && (
          <div className="text-gray-400 italic">"{intent.reasoning}"</div>
        )}

        <div className="space-y-1">
          {run.traces.map((t) => (
            <div key={t.task_id} className="flex gap-2 items-center text-[11px]">
              <span
                className={cn(
                  "px-1.5 py-0.5 rounded font-mono uppercase tracking-wide",
                  STATUS_STYLES[t.status],
                )}
              >
                {t.status}
              </span>
              <code className="text-gray-300">{t.task_type}</code>
              <span className="text-gray-500">→ {t.agent_name}</span>
              <span className="ml-auto text-gray-600">{t.latency_ms} ms</span>
            </div>
          ))}
        </div>

        <details className="text-gray-500">
          <summary className="cursor-pointer hover:text-gray-300 select-none">
            graph ({graph.nodes.length} node)
          </summary>
          <ul className="mt-2 space-y-1 font-mono text-[11px] text-gray-400">
            {graph.nodes.map((n) => (
              <li key={n.task_id}>
                {n.task_type} → <span className="text-gray-500">{n.required_agent}</span>
                {n.depends_on.length > 0 && (
                  <span className="text-gray-600"> · deps: {n.depends_on.map((d) => d.slice(0, 6)).join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
        </details>

        {observation.ocr_text && (
          <details className="text-gray-500">
            <summary className="cursor-pointer hover:text-gray-300 select-none">
              OCR text ({observation.ocr_text.length} chars)
            </summary>
            <pre className="mt-2 p-2 bg-black/40 border border-white/5 rounded text-[11px] text-gray-400 whitespace-pre-wrap max-h-60 overflow-auto">
              {observation.ocr_text}
            </pre>
          </details>
        )}
      </div>
    </details>
  );
}

function LoadingBubble({ label }: { label: string }) {
  return (
    <div className="flex justify-start">
      <div className="bg-white/5 border border-white/10 rounded-2xl px-5 py-4">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <span className="text-gray-500 text-sm">{label || "Düşünüyor…"}</span>
        </div>
      </div>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function ImageIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
  );
}
