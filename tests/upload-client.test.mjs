import test from "node:test";
import assert from "node:assert/strict";
import { uploadFile } from "../studymate/static/lib/api.js";

for (const state of ["cancelled", "expired", "pending", "assembling"]) {
  test(`saved ${state} upload does not trap the same file in a retry loop`, async () => {
    const file = new File(["test"], "test.txt", { lastModified: 100 });
    const key = "studymate-upload:lecture:test.txt:4:100";
    const entries = new Map([[key, "old"]]);
    globalThis.localStorage = {
      getItem: k => entries.get(k),
      setItem: (k, v) => entries.set(k, v),
      removeItem: k => entries.delete(k),
    };
    const calls = [];
    globalThis.fetch = async (url, options) => {
      calls.push([url, options.method || "GET"]);
      if (url === "/api/uploads/old" && !options.method)
        return Response.json({ id: "old", status: state, expires_at: "2000-01-01T00:00:00Z", chunk_size: 1024 });
      if (url === "/api/uploads" && options.method === "POST")
        return Response.json({ id: "new", status: "pending", chunk_size: 1024 });
      return Response.json({ ok: true });
    };
    if (state === "assembling") {
      await assert.rejects(uploadFile(file, "lecture", () => {}), /조립/);
      assert.equal(calls.length, 1);
      assert.equal(entries.get(key), "old");
    } else {
      await uploadFile(file, "lecture", () => {});
      assert.ok(calls.some(([url, method]) => url === "/api/uploads" && method === "POST"));
      assert.ok(calls.some(([url]) => url === "/api/uploads/new/complete"));
      assert.equal(calls.some(([url, method]) => url === "/api/uploads/old" && method === "DELETE"), state === "pending");
      assert.equal(entries.has(key), false);
    }
  });
}
