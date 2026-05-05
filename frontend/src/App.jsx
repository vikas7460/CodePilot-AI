import { useMemo, useState } from "react";
import "./App.css";
import * as api from "./api";

const VIEWS = {
  REPO: "repo",
  AI: "ai",
  FILES: "files",
  TESTS: "tests",
  GIT: "git",
  OUTPUT: "output",
};

const NAV_ITEMS = [
  { id: VIEWS.REPO, label: "Repo Setup", helper: "Clone, files, index" },
  { id: VIEWS.AI, label: "AI Tasks", helper: "Ask, agents, patch" },
  { id: VIEWS.FILES, label: "File Tools", helper: "Read, write, edit" },
  { id: VIEWS.TESTS, label: "Test + Debug", helper: "Tests, debug loop" },
  { id: VIEWS.GIT, label: "Git + PR", helper: "Diff, commit, PR" },
  { id: VIEWS.OUTPUT, label: "Output", helper: "API response" },
];

function App() {
  const [view, setView] = useState(VIEWS.REPO);
  const [loading, setLoading] = useState(false);
  const [backendOk, setBackendOk] = useState("unknown");
  const [output, setOutput] = useState(null);
  const [lastAction, setLastAction] = useState("No action yet");
  const [runningAction, setRunningAction] = useState("");

  const [repoUrl, setRepoUrl] = useState("https://github.com/psf/requests.git");
  const [repoId, setRepoId] = useState("");
  const [files, setFiles] = useState([]);

  const [task, setTask] = useState("explain authentication");

  const [filePath, setFilePath] = useState("src/requests/auth.py");
  const [fileContent, setFileContent] = useState("");
  const [changeMode, setChangeMode] = useState("append");
  const [oldText, setOldText] = useState("");
  const [newText, setNewText] = useState("\n# frontend test change\n");

  const [testTarget, setTestTarget] = useState("");
  const [forceInstall, setForceInstall] = useState(false);

  const [rollbackPath, setRollbackPath] = useState("src/requests/auth.py");
  const [deleteUntracked, setDeleteUntracked] = useState(false);
  const [commitMessage, setCommitMessage] = useState("AI fix: update code");
  const [branchName, setBranchName] = useState("");
  const [prTitle, setPrTitle] = useState("AI Fix");
  const [prBody, setPrBody] = useState(
    "This PR was created by the AI Software Engineer backend."
  );

  const outputSummary = useMemo(() => {
    if (!output) return "No backend response yet.";
    if (typeof output === "string") return output;
    if (output.message) return output.message;
    if (output._from_cache) return "Loaded instantly from frontend cache.";
    if (output.repo_id) return `Response received for repo: ${output.repo_id}`;
    return "Backend response received.";
  }, [output]);

  async function runAction(label, action, goToOutput = true) {
    if (loading) return null;

    try {
      setLoading(true);
      setRunningAction(label);
      setLastAction(label);

      const data = await action();

      setOutput(data);

      if (goToOutput) {
        setView(VIEWS.OUTPUT);
      }

      return data;
    } catch (error) {
      setOutput(error);
      setView(VIEWS.OUTPUT);
      return null;
    } finally {
      setLoading(false);
      setRunningAction("");
    }
  }

  async function handleHealthCheck() {
    const data = await runAction("Health Check", () => api.healthCheck(), false);
    if (data?.status === "healthy") setBackendOk("online");
    else setBackendOk("offline");
  }

  async function handleClone() {
    const data = await runAction("Clone Repo", () => api.cloneRepo(repoUrl), true);
    if (data?.repo_id) setRepoId(data.repo_id);
  }

  async function handleGetFiles() {
    const data = await runAction("Get Files", () => api.getRepoFiles(repoId), false);
    setFiles(data?.files || []);
  }

  async function handleReadFile() {
    const data = await runAction("Read File", () => api.readFile(repoId, filePath), false);
    if (data?.content !== undefined) setFileContent(data.content);
  }

  async function handleWriteFile() {
    await runAction("Write File", () =>
      api.writeFile(repoId, filePath, fileContent)
    );
  }

  async function handleApplyChange() {
    const payload = {
      file_path: filePath,
      mode: changeMode,
      old_text: changeMode === "replace_text" ? oldText : null,
      new_text: newText,
      backup: true,
    };

    await runAction("Apply Change", () => api.applyChange(repoId, payload));
  }

  function openFile(file) {
    setFilePath(file);
    setRollbackPath(file);
    setView(VIEWS.FILES);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">AI</div>
          <div>
            <h1>AI Engineer</h1>
            <p>Autonomous coding platform</p>
          </div>
        </div>

        <nav className="side-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={view === item.id ? "nav-item active" : "nav-item"}
              onClick={() => setView(item.id)}
              title={item.helper}
            >
              <span>{item.label}</span>
              <small>{item.helper}</small>
            </button>
          ))}
        </nav>

        <div className="repo-card">
          <span className="label-small">Repo ID</span>
          <div className="repo-id">{repoId || "No repo selected"}</div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h2>{NAV_ITEMS.find((item) => item.id === view)?.label}</h2>
            <p>{NAV_ITEMS.find((item) => item.id === view)?.helper}</p>
          </div>

          <div className="top-actions">
            <button
              onClick={handleHealthCheck}
              disabled={loading}
              title="Check whether backend is reachable"
            >
              Check Backend
            </button>

            <div className={`status-pill ${loading ? "loading" : ""}`}>
              {loading ? `Running ${runningAction}...` : "Ready"}
            </div>
          </div>
        </header>

        <section className="status-grid">
          <div className="mini-card">
            <span>Backend</span>
            <strong className={backendOk === "online" ? "green" : ""}>
              {backendOk === "online" ? "Online" : "127.0.0.1:8000"}
            </strong>
          </div>

          <div className="mini-card">
            <span>Last Action</span>
            <strong>{lastAction}</strong>
          </div>

          <div className="mini-card">
            <span>Cache</span>
            <strong>{output?._from_cache ? "Used" : "Fresh/Empty"}</strong>
          </div>
        </section>

        {view === VIEWS.REPO && (
          <section className="content-grid">
            <div className="panel">
              <h3>Repository Setup</h3>

              <label>GitHub Repo URL</label>
              <input
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/psf/requests.git"
              />

              <button
                className="primary"
                onClick={handleClone}
                disabled={loading || !repoUrl}
                title="Clone the GitHub repository into backend/repos and return a repo_id"
              >
                Clone Repo
              </button>

              <label>Repo ID</label>
              <input
                value={repoId}
                onChange={(e) => setRepoId(e.target.value)}
                placeholder="repo_id appears here after clone"
              />

              <div className="button-row">
                <button
                  onClick={handleGetFiles}
                  disabled={loading || !repoId}
                  title="Fetch file list from cloned repository; uses frontend cache on repeated clicks"
                >
                  Get Files
                </button>

                <button
                  onClick={() =>
                    runAction("Index Repo", () => api.indexRepo(repoId))
                  }
                  disabled={loading || !repoId}
                  title="Chunk code and store embeddings in vector database"
                >
                  Index Repo
                </button>
              </div>
            </div>

            <div className="panel">
              <h3>Repository Files</h3>

              {files.length === 0 ? (
                <p className="muted">No files loaded yet.</p>
              ) : (
                <div className="file-list">
                  {files.map((file) => (
                    <button
                      key={file}
                      className="file-button"
                      onClick={() => openFile(file)}
                      title="Open this file in File Tools"
                    >
                      {file}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}

        {view === VIEWS.AI && (
          <section className="panel full">
            <h3>AI Task Runner</h3>

            <label>Repo ID</label>
            <input value={repoId} onChange={(e) => setRepoId(e.target.value)} />

            <label>Task / Question</label>
            <textarea rows="7" value={task} onChange={(e) => setTask(e.target.value)} />

            <div className="button-row wrap">
              <button
                onClick={() => runAction("Ask Repo", () => api.askRepo(repoId, task))}
                disabled={loading || !repoId || !task}
                title="Ask a RAG-based question; repeated same question uses short frontend cache"
              >
                Ask Repo
              </button>

              <button
                onClick={() => runAction("Agent Ask", () => api.agentAsk(repoId, task, true))}
                disabled={loading || !repoId || !task}
                title="Run planner, researcher, answer and reviewer agents"
              >
                Agent Ask
              </button>

              <button
                onClick={() => runAction("Auto Patch", () => api.autoPatch(repoId, task))}
                disabled={loading || !repoId || !task}
                title="Generate and apply a safe AI code patch"
              >
                Auto Patch
              </button>
            </div>
          </section>
        )}

        {view === VIEWS.FILES && (
          <section className="panel full">
            <h3>File Tools</h3>

            <label>Repo ID</label>
            <input value={repoId} onChange={(e) => setRepoId(e.target.value)} />

            <label>File Path</label>
            <input value={filePath} onChange={(e) => setFilePath(e.target.value)} />

            <div className="button-row wrap">
              <button onClick={handleReadFile} disabled={loading || !repoId || !filePath} title="Read selected file content; repeated same file can use frontend cache">
                Read File
              </button>

              <button onClick={handleWriteFile} disabled={loading || !repoId || !filePath} title="Overwrite selected file with editor content and clear frontend cache">
                Write File
              </button>
            </div>

            <label>File Content</label>
            <textarea className="code-editor" rows="18" value={fileContent} onChange={(e) => setFileContent(e.target.value)} />

            <div className="divider" />

            <h3>Manual Apply Change</h3>

            <label>Change Mode</label>
            <select value={changeMode} onChange={(e) => setChangeMode(e.target.value)}>
              <option value="append">append</option>
              <option value="replace_text">replace_text</option>
            </select>

            {changeMode === "replace_text" && (
              <>
                <label>Old Text</label>
                <textarea rows="5" value={oldText} onChange={(e) => setOldText(e.target.value)} />
              </>
            )}

            <label>New Text</label>
            <textarea rows="5" value={newText} onChange={(e) => setNewText(e.target.value)} />

            <button className="primary" onClick={handleApplyChange} disabled={loading || !repoId || !filePath || !newText} title="Apply manual text change with backup enabled and clear cache">
              Apply Change
            </button>
          </section>
        )}

        {view === VIEWS.TESTS && (
          <section className="panel full">
            <h3>Test + Debug</h3>

            <label>Repo ID</label>
            <input value={repoId} onChange={(e) => setRepoId(e.target.value)} />

            <label>Test Target Optional</label>
            <input value={testTarget} onChange={(e) => setTestTarget(e.target.value)} placeholder="tests/test_requests.py::TestRequests::test_invalid_ca_certificate_path" />

            <label className="checkbox-row">
              <input type="checkbox" checked={forceInstall} onChange={(e) => setForceInstall(e.target.checked)} />
              Force dependency install
            </label>

            <div className="button-row wrap">
              <button onClick={() => runAction("Run Tests", () => api.runTests(repoId, testTarget, forceInstall))} disabled={loading || !repoId} title="Run full suite or targeted test">
                Run Tests
              </button>

              <button onClick={() => runAction("Auto Debug", () => api.autoDebug(repoId))} disabled={loading || !repoId} title="Run Debug Agent using cached failures when available">
                Auto Debug
              </button>
            </div>
          </section>
        )}

        {view === VIEWS.GIT && (
          <section className="panel full">
            <h3>Git + Pull Request</h3>

            <label>Repo ID</label>
            <input value={repoId} onChange={(e) => setRepoId(e.target.value)} />

            <div className="button-row wrap">
              <button onClick={() => runAction("Git Status", () => api.gitStatus(repoId))} disabled={loading || !repoId} title="Show current git status; short frontend cache is used">
                Git Status
              </button>

              <button onClick={() => runAction("Git Diff", () => api.gitDiff(repoId))} disabled={loading || !repoId} title="Show full git diff; short frontend cache is used">
                Git Diff
              </button>

              <button onClick={() => runAction("Diff Stat", () => api.gitDiffStat(repoId))} disabled={loading || !repoId} title="Show changed file summary">
                Diff Stat
              </button>
            </div>

            <div className="divider" />

            <h3>Rollback</h3>

            <label>Rollback File Path</label>
            <input value={rollbackPath} onChange={(e) => setRollbackPath(e.target.value)} />

            <div className="button-row wrap">
              <button onClick={() => runAction("Rollback File", () => api.rollbackFile(repoId, rollbackPath))} disabled={loading || !repoId || !rollbackPath} title="Rollback one file and clear frontend cache">
                Rollback File
              </button>

              <button onClick={() => runAction("Rollback All", () => api.rollbackAll(repoId, deleteUntracked))} disabled={loading || !repoId} title="Rollback all tracked changes and clear frontend cache">
                Rollback All
              </button>
            </div>

            <label className="checkbox-row">
              <input type="checkbox" checked={deleteUntracked} onChange={(e) => setDeleteUntracked(e.target.checked)} />
              Delete untracked files during rollback-all
            </label>

            <div className="divider" />

            <h3>Commit</h3>

            <label>Commit Message</label>
            <input value={commitMessage} onChange={(e) => setCommitMessage(e.target.value)} />

            <label>Branch Name Optional</label>
            <input value={branchName} onChange={(e) => setBranchName(e.target.value)} />

            <button className="primary" onClick={() => runAction("Commit Changes", () => api.commitChanges(repoId, commitMessage, branchName))} disabled={loading || !repoId || !commitMessage} title="Stage all changes, commit, and clear frontend cache">
              Commit Changes
            </button>

            <div className="divider" />

            <h3>Create Pull Request</h3>

            <label>PR Title</label>
            <input value={prTitle} onChange={(e) => setPrTitle(e.target.value)} />

            <label>PR Body</label>
            <textarea rows="5" value={prBody} onChange={(e) => setPrBody(e.target.value)} />

            <button className="primary" onClick={() => runAction("Create PR", () => api.createPR(repoId, prTitle, prBody))} disabled={loading || !repoId || !prTitle} title="Push current branch and create GitHub PR">
              Create PR
            </button>
          </section>
        )}

        {view === VIEWS.OUTPUT && (
          <section className="panel full">
            <div className="output-header">
              <div>
                <h3>API Output</h3>
                <p>{outputSummary}</p>
              </div>

              <button onClick={() => setOutput(null)} disabled={!output} title="Clear output">
                Clear Output
              </button>
            </div>

            <pre>{output ? JSON.stringify(output, null, 2) : "No output yet."}</pre>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;