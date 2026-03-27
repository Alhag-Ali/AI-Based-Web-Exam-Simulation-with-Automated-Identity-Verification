import React, { useState, useEffect } from "react";
import axios from "axios";

const API = "http://127.0.0.1:8000/api/students";

export default function ProfessorDashboard({ onCreateExam }) {
  const token = localStorage.getItem("token");
  const headers = { Authorization: `Token ${token}` };

  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    axios.get(`${API}/professor/dashboard/`, { headers })
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => { setError("Fehler beim Laden des Dashboards."); setLoading(false); });
  }, []);

  if (loading) return (
    <div className="card" style={{ textAlign: "center", padding: 40 }}>
      <div className="learn-spinner" style={{ margin: "0 auto 12px" }} />
      <p className="subtle">Dashboard wird geladen…</p>
    </div>
  );

  if (error) return (
    <div className="card" style={{ color: "var(--danger)", padding: 24 }}>❌ {error}</div>
  );

  const { total_exams, total_participants, exams } = data;
  const pastExams     = exams.filter(e => e.is_past).length;
  const upcomingExams = exams.filter(e => !e.is_past).length;

  return (
    <div className="stack-lg">

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16 }}>
        <StatCard icon="📋" label="Prüfungen gesamt" value={total_exams} color="var(--primary)" />
        <StatCard icon="👥" label="Teilnahmen gesamt" value={total_participants} color="var(--accent)" />
        <StatCard icon="✅" label="Vergangene Prüfungen" value={pastExams} color="var(--success)" />
        <StatCard icon="⏳" label="Bevorstehend" value={upcomingExams} color="var(--warning)" />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Meine Prüfungen</h3>
        <button className="btn" onClick={onCreateExam} style={{ fontSize: 13, padding: "8px 18px" }}>
          ➕ Neue Prüfung erstellen
        </button>
      </div>

      {exams.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "40px 24px", opacity: 0.7 }}>
          <div style={{ fontSize: 40, marginBottom: 10 }}>📭</div>
          <p style={{ fontWeight: 600, margin: "0 0 6px" }}>Noch keine Prüfungen erstellt</p>
          <p className="subtle" style={{ fontSize: 13 }}>Klicke auf "Neue Prüfung erstellen" um zu beginnen.</p>
        </div>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          {exams.map(exam => (
            <ExamCard
              key={exam.id}
              exam={exam}
              expanded={expanded === exam.id}
              onToggle={() => setExpanded(expanded === exam.id ? null : exam.id)}
            />
          ))}
        </div>
      )}

    </div>
  );
}

function StatCard({ icon, label, value, color }) {
  return (
    <div className="card" style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 26 }}>{icon}</div>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>{value}</div>
      <div className="subtle" style={{ fontSize: 12 }}>{label}</div>
    </div>
  );
}

function ExamCard({ exam, expanded, onToggle }) {
  const examDate  = new Date(exam.date);
  const isPast    = exam.is_past;

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div
        style={{ padding: "16px 20px", cursor: "pointer", display: "flex", gap: 16, alignItems: "center" }}
        onClick={onToggle}
      >
        <div style={{
          width: 44, height: 44, borderRadius: 10, flexShrink: 0,
          background: isPast ? "rgba(255,255,255,0.06)" : "rgba(99,102,241,0.15)",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20
        }}>
          {isPast ? "✅" : "📅"}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 2 }}>{exam.title}</div>
          <div className="subtle" style={{ fontSize: 12, display: "flex", gap: 16, flexWrap: "wrap" }}>
            <span>📅 {examDate.toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" })} {examDate.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr</span>
            <span>⏱ {exam.duration_minutes} Min.</span>
            <span>❓ {exam.question_count} Fragen</span>
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center", flexShrink: 0 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: "var(--accent)" }}>{exam.participant_count}</div>
            <div className="subtle" style={{ fontSize: 11 }}>Teilnehmer</div>
          </div>
          <div style={{
            padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
            background: isPast ? "rgba(34,197,94,0.15)" : "rgba(99,102,241,0.15)",
            color: isPast ? "var(--success)" : "var(--primary)",
          }}>
            {isPast ? "Abgeschlossen" : "Bevorstehend"}
          </div>
          <span style={{ opacity: 0.4, fontSize: 12 }}>{expanded ? "▲" : "▼"}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "16px 20px" }}>
          {exam.description && (
            <p className="subtle" style={{ fontSize: 13, marginBottom: 16 }}>{exam.description}</p>
          )}

          {exam.students.length === 0 ? (
            <p className="subtle" style={{ fontSize: 13 }}>Noch keine Teilnehmer für diese Prüfung.</p>
          ) : (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>
                👥 Teilnehmer ({exam.students.length})
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
                {exam.students.map((s, i) => (
                  <div key={i} style={{
                    background: "rgba(255,255,255,0.04)", borderRadius: 8,
                    padding: "8px 12px", fontSize: 13,
                    display: "flex", flexDirection: "column", gap: 2
                  }}>
                    <div style={{ fontWeight: 600 }}>{s.name || s.email}</div>
                    <div className="subtle" style={{ fontSize: 11 }}>{s.email}</div>
                    <div className="subtle" style={{ fontSize: 11 }}>
                      Beigetreten: {new Date(s.joined_at).toLocaleString("de-DE")}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
