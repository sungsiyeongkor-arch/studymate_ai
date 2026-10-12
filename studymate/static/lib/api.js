export let csrf = "";
export function setCsrf(value) {
  csrf = value;
}
export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}), "X-CSRF-Token": csrf };
  if (
    options.body &&
    typeof options.body !== "string" &&
    !(options.body instanceof Blob)
  ) {
    options = { ...options, body: JSON.stringify(options.body) };
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch("/api" + path, { ...options, headers });
  const value = await response
    .json()
    .catch(() => ({ error: "서버 응답을 읽지 못했습니다." }));
  if (!response.ok) {
    const error = new Error(value.error || "요청에 실패했습니다.");
    error.status = response.status;
    throw error;
  }
  if (value.csrf) setCsrf(value.csrf);
  return value;
}

export async function uploadFile(file, lectureId, onProgress) {
  const fingerprint = `${lectureId}:${file.name}:${file.size}:${file.lastModified}`;
  const storageKey = "studymate-upload:" + fingerprint;
  let upload;
  const saved = localStorage.getItem(storageKey);
  if (saved) {
    try {
      upload = await api("/uploads/" + saved);
    } catch {
      localStorage.removeItem(storageKey);
    }
  }
  if (
    upload?.status === "pending" &&
    upload.expires_at &&
    Date.parse(upload.expires_at) < Date.now()
  ) {
    await api("/uploads/" + upload.id, { method: "DELETE" });
    upload = null;
    localStorage.removeItem(storageKey);
  }
  if (upload && ["cancelled", "expired"].includes(upload.status)) {
    upload = null;
    localStorage.removeItem(storageKey);
  }
  if (upload?.status === "assembling") {
    throw Error(
      "파일을 조립하고 있습니다. 잠시 후 다시 확인하세요. 계속 멈춰 있으면 운영자에게 복구를 요청하세요.",
    );
  }
  if (!upload) {
    upload = await api("/uploads", {
      method: "POST",
      body: { lecture_id: lectureId, name: file.name, size: file.size },
    });
    localStorage.setItem(storageKey, upload.id);
  }
  if (upload.status === "completed") {
    localStorage.removeItem(storageKey);
    return upload;
  }
  const received = new Set(upload.received || []);
  const total = Math.ceil(file.size / upload.chunk_size);
  for (let i = 0; i < total; i++) {
    if (!received.has(i)) {
      await api(`/uploads/${upload.id}/chunks/${i}`, {
        method: "PUT",
        body: file.slice(
          i * upload.chunk_size,
          Math.min(file.size, (i + 1) * upload.chunk_size),
        ),
        headers: { "Content-Type": "application/octet-stream" },
      });
    }
    onProgress(Math.round(((i + 1) / total) * 100));
  }
  const result = await api("/uploads/" + upload.id + "/complete", {
    method: "POST",
  });
  localStorage.removeItem(storageKey);
  return result;
}
