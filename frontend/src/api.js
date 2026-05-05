import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
});

const cache = new Map();

function cacheKey(name, params) {
  return `${name}:${JSON.stringify(params)}`;
}

function getCached(key) {
  const item = cache.get(key);
  if (!item) return null;

  const isExpired = Date.now() - item.time > item.ttl;
  if (isExpired) {
    cache.delete(key);
    return null;
  }

  return item.data;
}

function setCached(key, data, ttl = 30000) {
  cache.set(key, {
    data,
    ttl,
    time: Date.now(),
  });
}

export function clearApiCache() {
  cache.clear();
}

function handleApiError(error) {
  if (error.response) {
    throw error.response.data;
  }

  if (error.request) {
    throw {
      message:
        "Network error. Check backend is running on http://127.0.0.1:8000 and CORS is enabled.",
      details: error.message,
    };
  }

  throw {
    message: error.message,
  };
}

async function request(fn) {
  try {
    const res = await fn();
    return res.data;
  } catch (error) {
    handleApiError(error);
  }
}

async function cachedRequest(name, params, fn, ttl = 30000) {
  const key = cacheKey(name, params);
  const cached = getCached(key);

  if (cached) {
    return {
      ...cached,
      _from_cache: true,
    };
  }

  const data = await request(fn);
  setCached(key, data, ttl);

  return {
    ...data,
    _from_cache: false,
  };
}

export async function healthCheck() {
  return cachedRequest("health", {}, () => api.get("/health"), 10000);
}

export async function cloneRepo(repoUrl) {
  clearApiCache();
  return request(() => api.post("/repos/clone", { repo_url: repoUrl }));
}

export async function getRepoFiles(repoId) {
  return cachedRequest(
    "repo-files",
    { repoId },
    () => api.get(`/repos/${repoId}/files`),
    60000
  );
}

export async function indexRepo(repoId) {
  clearApiCache();
  return request(() => api.post(`/repos/${repoId}/index`));
}

export async function askRepo(repoId, question) {
  return cachedRequest(
    "ask-repo",
    { repoId, question },
    () =>
      api.get(`/repos/${repoId}/ask`, {
        params: { question },
      }),
    30000
  );
}

export async function agentAsk(repoId, task, review = true) {
  return request(() =>
    api.get(`/repos/${repoId}/agent-ask`, {
      params: { task, review },
    })
  );
}

export async function autoPatch(repoId, question) {
  clearApiCache();
  return request(() => api.post(`/repos/${repoId}/auto-patch`, { question }));
}

export async function readFile(repoId, filePath) {
  return cachedRequest(
    "read-file",
    { repoId, filePath },
    () =>
      api.post(`/repos/${repoId}/read-file`, {
        file_path: filePath,
      }),
    30000
  );
}

export async function writeFile(repoId, filePath, content) {
  clearApiCache();
  return request(() =>
    api.post(`/repos/${repoId}/write-file`, {
      file_path: filePath,
      content,
    })
  );
}

export async function applyChange(repoId, payload) {
  clearApiCache();
  return request(() => api.post(`/repos/${repoId}/apply-change`, payload));
}

export async function runTests(repoId, target = "", forceInstall = false) {
  return request(() =>
    api.post(`/repos/${repoId}/run-tests`, null, {
      params: {
        target: target || undefined,
        force_install: forceInstall,
      },
    })
  );
}

export async function autoDebug(repoId) {
  clearApiCache();
  return request(() => api.post(`/repos/${repoId}/auto-debug`));
}

export async function gitStatus(repoId) {
  return cachedRequest(
    "git-status",
    { repoId },
    () => api.get(`/repos/${repoId}/git-status`),
    8000
  );
}

export async function gitDiff(repoId) {
  return cachedRequest(
    "git-diff",
    { repoId },
    () => api.get(`/repos/${repoId}/git-diff`),
    8000
  );
}

export async function gitDiffStat(repoId) {
  return cachedRequest(
    "git-diff-stat",
    { repoId },
    () => api.get(`/repos/${repoId}/git-diff-stat`),
    8000
  );
}

export async function rollbackFile(repoId, filePath) {
  clearApiCache();
  return request(() =>
    api.post(`/repos/${repoId}/rollback-file`, {
      file_path: filePath,
    })
  );
}

export async function rollbackAll(repoId, deleteUntracked = false) {
  clearApiCache();
  return request(() =>
    api.post(`/repos/${repoId}/rollback-all`, {
      delete_untracked: deleteUntracked,
    })
  );
}

export async function commitChanges(repoId, message, branchName = "") {
  clearApiCache();

  const payload = { message };

  if (branchName) {
    payload.branch_name = branchName;
  }

  return request(() => api.post(`/repos/${repoId}/commit`, payload));
}

export async function createPR(repoId, title, body) {
  clearApiCache();

  return request(() =>
    api.post(`/repos/${repoId}/create-pr`, {
      title,
      body,
    })
  );
}