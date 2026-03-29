import React, { useRef, useState } from "react";
import axios from "axios";
import Webcam from "react-webcam";

const FACE_THRESHOLD = 0.55;

/**
 * Full-screen identity verification for one exam.
 * Props:
 *   exam      – exam object { id, title, date, … }
 *   onSuccess – called after successful verification + join (passes exam)
 *   onBack    – called when student wants to go back to the exam list
 */
function VerificationPage({ exam, onSuccess, onBack }) {
  const [step, setStep] = useState(1);          // 1=capture face, 2=capture ID, 3=compare
  const [faceDataUrl, setFaceDataUrl] = useState(null);
  const [idDataUrl,   setIdDataUrl]   = useState(null);

  const [ocrLoading, setOcrLoading] = useState(false);
  const [matrikelInput, setMatrikelInput] = useState("");

  const [verifying, setVerifying] = useState(false);
  const [verified,  setVerified]  = useState(false);
  const [message,   setMessage]   = useState("");
  const [details,   setDetails]   = useState(null);

  const [joining,     setJoining]     = useState(false);
  const [enrollError, setEnrollError] = useState(null);

  const webcamRef = useRef(null);
  const token = localStorage.getItem("token");

  /* ── helpers ── */
  const blob = async (dataUrl) => {
    const r = await fetch(dataUrl);
    return r.blob();
  };

  const resetAll = () => {
    setStep(1);
    setFaceDataUrl(null);
    setIdDataUrl(null);
    setMatrikelInput("");
    setOcrLoading(false);
    setVerified(false);
    setMessage("");
    setDetails(null);
    setEnrollError(null);
  };

  /* ── capture face ── */
  const captureFace = () => {
    const shot = webcamRef.current?.getScreenshot();
    if (!shot) return;
    setFaceDataUrl(shot);
    setVerified(false); setMessage(""); setDetails(null);
    setStep(2);
  };

  /* ── capture ID + auto-OCR ── */
  const captureId = async () => {
    const shot = webcamRef.current?.getScreenshot();
    if (!shot) return;
    setIdDataUrl(shot);
    setVerified(false); setMessage(""); setDetails(null);
    setMatrikelInput("");
    setStep(3);

    setOcrLoading(true);
    try {
      const idBlob = await blob(shot);
      const fd = new FormData();
      fd.append("id_image", idBlob, "id.jpg");
      const res = await axios.post(
        "http://127.0.0.1:8000/api/students/extract-matrikel/",
        fd,
        { headers: { Authorization: `Token ${token}`, "Content-Type": "multipart/form-data" } }
      );
      if (res.data.matrikel) setMatrikelInput(res.data.matrikel);
    } catch (_) {
      // silent – student can type manually
    } finally {
      setOcrLoading(false);
    }
  };

  /* ── full verification (face + matrikel + enrollment) ── */
  const verifyNow = async () => {
    if (!faceDataUrl || !idDataUrl) return;
    setVerifying(true);
    setVerified(false);
    setMessage("Verification in progress …");
    setDetails(null);

    try {
      const faceBlob = await blob(faceDataUrl);
      const idBlob   = await blob(idDataUrl);
      const fd = new FormData();
      fd.append("live_image", faceBlob, "live.jpg");
      fd.append("id_image",   idBlob,   "id.jpg");
      fd.append("exam_id", exam.id);
      if (matrikelInput.length === 7) fd.append("matrikel_input", matrikelInput);

      const res = await axios.post(
        "http://127.0.0.1:8000/api/students/verify-identity/",
        fd,
        { headers: { Authorization: `Token ${token}`, "Content-Type": "multipart/form-data" } }
      );
      setVerified(res.data.verified);
      setMessage(res.data.message || "");
      setDetails(res.data);
    } catch (err) {
      setVerified(false);
      setMessage(err.response?.data?.message || "Verification failed.");
      setDetails(err.response?.data || null);
    } finally {
      setVerifying(false);
    }
  };

  /* ── join exam after verification ── */
  const joinExam = async () => {
    if (!verified) return;
    setJoining(true);
    try {
      await axios.post(
        `http://127.0.0.1:8000/api/students/exams/${exam.id}/join/`,
        {},
        { headers: { Authorization: `Token ${token}` } }
      );
      onSuccess(exam);
    } catch (err) {
      const errData = err.response?.data;
      if (errData?.error === "not_enrolled") {
        setEnrollError(errData.message || "You are not authorized for this exam.");
      } else {
        alert(errData?.message || "Error joining the exam.");
      }
    } finally {
      setJoining(false);
    }
  };

  /* ── request manual help ── */
  const requestHelp = async () => {
    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/api/students/help-request/",
        { exam_id: exam.id, message: "Verification failed or problematic. Please check manually." },
        { headers: { Authorization: `Token ${token}` } }
      );
      alert(res.data?.message || "The provider has been notified.");
    } catch (_) { alert("Could not send help request."); }
  };

  /* ── render ── */
  return (
    <div className="stack-lg">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn secondary" onClick={onBack} style={{ flexShrink: 0 }}>
          ← Back
        </button>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>🧾 Identity Verification</h2>
          <p style={{ margin: 0, color: "var(--muted)", fontSize: 13 }}>
            Exam: <b>{exam.title}</b> &nbsp;·&nbsp; {exam.date}
          </p>
        </div>
      </div>

      {/* Steps indicator */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
        <StepBadge n={1} label="Capture Face"  active={step === 1} done={step > 1} />
        <span style={{ color: "var(--muted)" }}>→</span>
        <StepBadge n={2} label="Capture ID"    active={step === 2} done={step > 2} />
        <span style={{ color: "var(--muted)" }}>→</span>
        <StepBadge n={3} label="Compare"        active={step >= 3}  done={verified} />
      </div>

      {/* Enrollment error */}
      {enrollError && (
        <div className="card" style={{ borderColor: "rgba(239,68,68,.4)", background: "rgba(239,68,68,.08)" }}>
          <div style={{ display: "flex", gap: 12 }}>
            <span style={{ fontSize: 22 }}>🚫</span>
            <div>
              <div style={{ fontWeight: 700, color: "#fca5a5" }}>Not authorized</div>
              <div style={{ color: "#fecaca", fontSize: 14 }}>{enrollError}</div>
            </div>
          </div>
        </div>
      )}

      {/* Webcam */}
      <Webcam
        ref={webcamRef}
        audio={false}
        screenshotFormat="image/jpeg"
        width={480}
        height={360}
        videoConstraints={{ facingMode: "user" }}
        style={{ borderRadius: 12, border: "1px solid rgba(255,255,255,0.14)", width: "100%", maxWidth: 560 }}
      />

      {/* Action buttons */}
      <div className="btn-group">
        {step === 1 && <button className="btn" onClick={captureFace}>📷 Capture Face</button>}
        {step >= 2 && <button className="btn secondary" onClick={() => { setFaceDataUrl(null); setIdDataUrl(null); setMatrikelInput(""); setOcrLoading(false); setVerified(false); setMessage(""); setDetails(null); setStep(1); }}>↩ Retake Face</button>}
        {step === 2 && <button className="btn" onClick={captureId}>🪪 Capture ID</button>}
        {step >= 3 && <button className="btn secondary" onClick={() => { setIdDataUrl(null); setMatrikelInput(""); setOcrLoading(false); setVerified(false); setMessage(""); setDetails(null); setStep(2); }}>↩ Retake ID</button>}
        <button
          className="btn warning"
          onClick={verifyNow}
          disabled={!faceDataUrl || !idDataUrl || verifying || matrikelInput.length !== 7}
          title={matrikelInput.length !== 7 ? "Enter your 7-digit matriculation number first" : ""}
        >
          🔍 Compare
        </button>
        <button className="btn secondary" onClick={requestHelp}>🆘 Request Help</button>
        <button
          className={verified ? "btn success" : "btn secondary"}
          onClick={joinExam}
          disabled={!verified || joining}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              width: 10, height: 10, borderRadius: 999,
              background: verified ? "#16a34a" : "rgba(255,255,255,.25)",
              boxShadow: verified ? "0 0 0 6px rgba(22,163,74,.18)" : "none"
            }} />
            {joining ? "Joining…" : verified ? "✅ Join Exam" : "Join Exam"}
          </span>
        </button>
      </div>

      {/* Preview thumbnails */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Preview title="Face" dataUrl={faceDataUrl} />
        <Preview title="ID"   dataUrl={idDataUrl} />
      </div>

      {/* Matriculation number input – visible after ID capture */}
      {step >= 3 && (
        <div style={{ padding: "14px 16px", background: "rgba(255,255,255,0.04)", borderRadius: 10, border: "1px solid rgba(255,255,255,0.12)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>🔢 Matriculation Number</span>
            {ocrLoading && <span style={{ fontSize: 12, color: "#60a5fa" }}>⏳ Reading ID card…</span>}
            {!ocrLoading && matrikelInput && <span style={{ fontSize: 12, color: "#a3e635" }}>✦ Pre-filled by OCR — edit if incorrect</span>}
            {!ocrLoading && !matrikelInput && <span style={{ fontSize: 12, color: "#fbbf24" }}>⚠️ OCR could not read — enter manually</span>}
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input
              type="text"
              inputMode="numeric"
              maxLength={7}
              value={matrikelInput}
              disabled={ocrLoading}
              onChange={(e) => {
                const raw = e.target.value.replace(/\D/g, "").slice(0, 7);
                setMatrikelInput(raw);
                setVerified(false); setMessage(""); setDetails(null);
              }}
              placeholder={ocrLoading ? "Reading…" : "e.g. 8053932"}
              style={{
                background: ocrLoading ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.08)",
                border: matrikelInput.length === 7 ? "1.5px solid #22c55e" : "1.5px solid rgba(255,255,255,0.22)",
                borderRadius: 8, color: ocrLoading ? "#6b7280" : "#fff",
                fontSize: 22, fontWeight: 700, letterSpacing: 4,
                padding: "8px 14px", width: 170, outline: "none",
              }}
            />
            <span style={{ fontSize: 13, color: matrikelInput.length === 7 ? "#22c55e" : "var(--muted)" }}>
              {matrikelInput.length === 7 ? "✅ 7 digits" : `${matrikelInput.length} / 7 digits`}
            </span>
          </div>
          {matrikelInput.length > 0 && matrikelInput.length < 7 && (
            <p style={{ margin: "6px 0 0", fontSize: 12, color: "#fbbf24" }}>⚠️ Exactly 7 digits required.</p>
          )}
        </div>
      )}

      {/* Verification result */}
      <div>
        {verifying && <p className="subtle">⏳ Verification in progress …</p>}
        {message && (
          <div className="card" style={{ borderColor: verified ? "rgba(34,197,94,.35)" : "rgba(239,68,68,.35)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{
                width: 12, height: 12, borderRadius: 999, flexShrink: 0,
                background: verified ? "#22c55e" : "#ef4444",
                boxShadow: verified ? "0 0 0 6px rgba(34,197,94,.15)" : "0 0 0 6px rgba(239,68,68,.15)"
              }} />
              <span style={{ fontWeight: 700, color: verified ? "#22c55e" : "#ef4444" }}>{message}</span>
            </div>
          </div>
        )}

        {details && (
          <div className="card" style={{ fontSize: 13, marginTop: 8 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
              <Pill label="Face detected (live)" ok={details.face_detected_live} />
              <Pill label="Face detected (ID)"   ok={details.face_detected_id} />
              <Pill label="Faces match"          ok={details.face_matched} />
              <Pill label="Matrikel verified"    ok={details.matrikel_match} />
              {details.enrolled != null && <Pill label="Enrolled in exam" ok={details.enrolled} />}
            </div>

            {/* Matrikel comparison */}
            <div style={{ marginBottom: 8, padding: "8px 12px", background: "rgba(255,255,255,0.04)", borderRadius: 8 }}>
              <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 2 }}>YOU ENTERED</div>
                  <b style={{ fontSize: 17, letterSpacing: 2 }}>{details.matrikel_input ?? matrikelInput}</b>
                </div>
                <span style={{ color: "var(--muted)", fontSize: 16 }}>vs</span>
                <div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 2 }}>READ FROM ID CARD (OCR)</div>
                  <b style={{ fontSize: 17, letterSpacing: 2, color: details.matrikel_extracted ? "#e2e8f0" : "#f87171" }}>
                    {details.matrikel_extracted ?? "— not readable"}
                  </b>
                </div>
                <div>
                  {details.matrikel_match
                    ? <span style={{ color: "#22c55e", fontWeight: 700 }}>✅ Match</span>
                    : <span style={{ color: "#f87171", fontWeight: 700 }}>❌ Mismatch</span>}
                </div>
              </div>
              {!details.matrikel_extracted && (
                <p style={{ margin: "6px 0 0", fontSize: 12, color: "#fbbf24" }}>
                  💡 OCR could not read the number — hold the ID flat with good lighting and retry.
                </p>
              )}
            </div>

            {details.face_similarity != null && (
              <p style={{ margin: "0 0 6px" }} className="subtle">
                Face similarity: <b>{(details.face_similarity * 100).toFixed(1)} %</b>
                {" "}(threshold: {(FACE_THRESHOLD * 100).toFixed(0)} %)
              </p>
            )}

            {details.hints?.length > 0 && (
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                {details.hints.map((h, i) => <li key={i} style={{ marginBottom: 2 }}>💡 {h}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── small sub-components ── */

function StepBadge({ n, label, active, done }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "4px 10px", borderRadius: 999,
      background: done ? "rgba(34,197,94,.15)" : active ? "rgba(96,165,250,.15)" : "rgba(255,255,255,.06)",
      border: done ? "1px solid rgba(34,197,94,.4)" : active ? "1px solid rgba(96,165,250,.4)" : "1px solid rgba(255,255,255,.1)",
      color: done ? "#22c55e" : active ? "#60a5fa" : "var(--muted)",
      fontWeight: 600,
    }}>
      {done ? "✓" : n} {label}
    </span>
  );
}

function Preview({ title, dataUrl }) {
  return (
    <div style={{ width: 180 }}>
      <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>{title}</div>
      <div style={{
        width: 180, height: 130, background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.14)", borderRadius: 8,
        display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden"
      }}>
        {dataUrl
          ? <img src={dataUrl} alt={title} style={{ width: "100%" }} />
          : <span style={{ color: "var(--muted)", fontSize: 12 }}>no image yet</span>}
      </div>
    </div>
  );
}

function Pill({ label, ok }) {
  return (
    <span style={{
      padding: "4px 10px", borderRadius: 999,
      background: ok ? "#dcfce7" : "#fee2e2",
      border: ok ? "1px solid #bbf7d0" : "1px solid #fecaca",
      fontSize: 12.5, fontWeight: 600,
      color: ok ? "#166534" : "#991b1b",
      boxShadow: ok ? "0 4px 12px rgba(34,197,94,.18)" : "0 4px 12px rgba(239,68,68,.18)"
    }}>
      {label}: {ok ? "✅" : "❌"}
    </span>
  );
}

export default VerificationPage;
