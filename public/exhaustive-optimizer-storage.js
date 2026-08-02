const DB_NAME = "backteststock-exhaustive-optimizer-v1";
const DB_VERSION = 1;
const JOB_STORE = "jobs";
const CHUNK_STORE = "chunks";

function requestPromise(request) {
  return new Promise((resolve, reject) => {
    request.addEventListener("success", () => resolve(request.result));
    request.addEventListener("error", () => reject(request.error));
  });
}

function transactionPromise(transaction) {
  return new Promise((resolve, reject) => {
    transaction.addEventListener("complete", () => resolve());
    transaction.addEventListener("abort", () => reject(transaction.error));
    transaction.addEventListener("error", () => reject(transaction.error));
  });
}

export async function openOptimizerDb() {
  const request = indexedDB.open(DB_NAME, DB_VERSION);
  request.addEventListener("upgradeneeded", () => {
    const db = request.result;
    if (!db.objectStoreNames.contains(JOB_STORE)) {
      const jobs = db.createObjectStore(JOB_STORE, { keyPath: "id" });
      jobs.createIndex("updatedAt", "updatedAt");
      jobs.createIndex("status", "status");
    }
    if (!db.objectStoreNames.contains(CHUNK_STORE)) {
      const chunks = db.createObjectStore(CHUNK_STORE, { keyPath: "id" });
      chunks.createIndex("jobId", "jobId");
      chunks.createIndex("jobChunk", ["jobId", "chunkIndex"], { unique: true });
    }
  });
  return requestPromise(request);
}

export async function saveJob(job) {
  const db = await openOptimizerDb();
  const transaction = db.transaction(JOB_STORE, "readwrite");
  transaction.objectStore(JOB_STORE).put({
    ...job,
    updatedAt: new Date().toISOString(),
  });
  await transactionPromise(transaction);
  db.close();
}

export async function getJob(jobId) {
  const db = await openOptimizerDb();
  const transaction = db.transaction(JOB_STORE, "readonly");
  const result = await requestPromise(transaction.objectStore(JOB_STORE).get(jobId));
  db.close();
  return result || null;
}

export async function listJobs() {
  const db = await openOptimizerDb();
  const transaction = db.transaction(JOB_STORE, "readonly");
  const results = await requestPromise(transaction.objectStore(JOB_STORE).getAll());
  db.close();
  return [...results].sort((left, right) => String(right.updatedAt).localeCompare(String(left.updatedAt)));
}

export async function saveChunk(jobId, chunk) {
  const db = await openOptimizerDb();
  const transaction = db.transaction(CHUNK_STORE, "readwrite");
  transaction.objectStore(CHUNK_STORE).put({
    id: `${jobId}:${chunk.chunkIndex}`,
    jobId,
    chunkIndex: chunk.chunkIndex,
    startRank: chunk.startRank,
    count: chunk.completed,
    elapsedMs: chunk.elapsedMs,
    holdingCount: chunk.holdingCount,
    metricCount: chunk.metricCount,
    combinations: chunk.combinations,
    metrics: chunk.metrics,
    savedAt: new Date().toISOString(),
  });
  await transactionPromise(transaction);
  db.close();
}

export async function getChunk(jobId, chunkIndex) {
  const db = await openOptimizerDb();
  const transaction = db.transaction(CHUNK_STORE, "readonly");
  const result = await requestPromise(
    transaction.objectStore(CHUNK_STORE).index("jobChunk").get([jobId, chunkIndex]),
  );
  db.close();
  return result || null;
}

export async function listChunks(jobId) {
  const db = await openOptimizerDb();
  const transaction = db.transaction(CHUNK_STORE, "readonly");
  const request = transaction.objectStore(CHUNK_STORE).index("jobId").getAll(jobId);
  const results = await requestPromise(request);
  db.close();
  return [...results].sort((left, right) => left.chunkIndex - right.chunkIndex);
}

export async function deleteJob(jobId) {
  const db = await openOptimizerDb();
  const transaction = db.transaction([JOB_STORE, CHUNK_STORE], "readwrite");
  transaction.objectStore(JOB_STORE).delete(jobId);
  const index = transaction.objectStore(CHUNK_STORE).index("jobId");
  const cursorRequest = index.openKeyCursor(IDBKeyRange.only(jobId));
  cursorRequest.addEventListener("success", () => {
    const cursor = cursorRequest.result;
    if (!cursor) return;
    transaction.objectStore(CHUNK_STORE).delete(cursor.primaryKey);
    cursor.continue();
  });
  await transactionPromise(transaction);
  db.close();
}

export async function clearAllJobs() {
  const db = await openOptimizerDb();
  const transaction = db.transaction([JOB_STORE, CHUNK_STORE], "readwrite");
  transaction.objectStore(JOB_STORE).clear();
  transaction.objectStore(CHUNK_STORE).clear();
  await transactionPromise(transaction);
  db.close();
}
