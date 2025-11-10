import React, { useEffect, useRef, useState } from "react";
import Webcam from "react-webcam";
import axios from "axios";

export default function LiveVerification({ exam, onVerified }) {
  const webcamRef = useRef(null);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(true);
  const token = localStorage.getItem("token");

  useEffect(() => {
    if (!running) return;
    const interval = setInterval(async () => {
      const imageSrc = webcamRef.current?.getScreenshot();
      if (!imageSrc) return;

      const blob = await (await fetch(imageSrc)).blob();
      const form = new FormData();
      form.append("frame", blob, "frame.jpg");

      try {
        const res = await axios.post(
          "http://127.0.0.1:8000/api/students/live-verify/",
          form,
          {
            headers: {
              Authorization: `Token ${token}`,
              "Content-Type": "multipart/form-data",
            },
          }
        );
        setResult(res.data);
        if (res.data.verified) {
          setRunning(false);
          onVerified && onVerified();
        }
      } catch (err) {
        console.error(err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [running, token, onVerified]);

  return (
    <div style={{ padding: 20 }}>
      <h3>🧾 Live-Identitätsprüfung für {exam.title}</h3>
      <p>Halte dein Gesicht in die obere Box und deinen Studentenausweis in die untere.</p>

      <div style={{ position: "relative", display: "inline-block" }}>
        <Webcam
          ref={webcamRef}
          audio={false}
          screenshotFormat="image/jpeg"
          width={480}
          height={360}
          videoConstraints={{ facingMode: "user" }}
        />
        <div
          style={{
            position: "absolute",
            top: "10%",
            left: "5%",
            width: "90%",
            height: "45%",
            border: "2px dashed #00f",
            borderRadius: "8px",
          }}
        ></div>
        <div
          style={{
            position: "absolute",
            bottom: "5%",
            left: "5%",
            width: "90%",
            height: "25%",
            border: "2px dashed #0a0",
            borderRadius: "8px",
          }}
        ></div>
      </div>

      {result && (
        <div style={{ marginTop: 15 }}>
          <p><strong>Gesicht erkannt:</strong> {String(result.face_detected)}</p>
          <p><strong>Ausweis erkannt:</strong> {String(result.id_face_detected)}</p>
          <p><strong>Name-Match:</strong> {String(result?.db_compare?.name_match)}</p>
          <p><strong>Matrikelnummer-Match:</strong> {String(result?.db_compare?.matriculation_match)}</p>
          <p><strong>Gesichter stimmen überein:</strong> {String(result.faces_verified)}</p>
        </div>
      )}

      {!running && result?.verified && (
        <p style={{ color: "green" }}>✅ Identität bestätigt – du kannst jetzt beitreten!</p>
      )}
    </div>
  );
}

