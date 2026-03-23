import re

with open(r'c:\Anti Project\ResearchOS\frontend\src\components\OverviewTab.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace everything from `  return (` to the end of the `  return (` block.
# Actually, it's safer to just replace the whole `return (` block.

start_idx = content.find('  return (\n    <div className="content-grid workspace-grid">')
# Find the matching closing `</div>\n  );`
end_idx = content.find('  );\n}\n', start_idx) + 5

if start_idx == -1 or end_idx < start_idx:
    print("Could not find return block")
    exit(1)

new_return_block = """  return (
    <div className="dashboard-layout">
      {/* 1. Stat Cards Row */}
      {props.selectedProject && props.projectDashboard ? (
        <div className="stats-row">
          <StatCard 
            label="Papers Ingested" 
            value={props.projectTasks.filter(t => t.kind === "paper_ingest" && t.status === "succeeded").length} 
            meta="Papers" 
          />
          <StatCard 
            label="Research Gaps" 
            value={props.projectTasks.filter(t => t.kind === "gap_mapping" && t.status === "succeeded").length} 
            meta="Identified" 
          />
          <StatCard 
            label="Candidate Directions" 
            value={candidates.length} 
            meta={candidates.length > 0 ? "High confidence" : ""} 
          />
          <StatCard 
            label="Pipeline Stage" 
            value={stageLabel(props.selectedProject.stage)} 
            meta={`Day ${stageIndex + 1} of ${PIPELINE_STEPS.length}`} 
          />
        </div>
      ) : null}

      {/* 2. Research Pipeline Row */}
      <Panel className="workspace-wide-panel">
        <div className="pipeline-header">
          <strong>Research Pipeline</strong>
          <span className="pipeline-status-text">Current stage: {stageLabel(props.selectedProject?.stage || "NEW_TOPIC")}</span>
          <span className="pipeline-completion-badge">{stageIndex} of {PIPELINE_STEPS.length} stages complete</span>
        </div>
        <div className="stage-pipeline">
          {PIPELINE_STEPS.map((step, index) => (
            <div
              key={step.label}
              className={
                stageIndex === index ? "stage-step active" : stageIndex > index ? "stage-step done" : "stage-step"
              }
            >
              <div className="stage-step-index">{stageIndex > index ? "✓" : index + 1}</div>
              <div className="stage-step-copy">
                <strong>{step.label}</strong>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      {/* 3. Three-Column Dashboard */}
      <div className="three-column-grid">
        {/* Left Column: Candidates */}
        <div className="dashboard-col candidates-col">
          <div className="dashboard-col-head">
            <strong>Top Candidate Directions</strong>
            <small>Ranked by overall score</small>
          </div>
          <div className="candidate-list-scroll">
            {filteredCandidates.length ? (
              filteredCandidates.map((candidate) => (
                <button
                  key={candidate.gapId}
                  type="button"
                  className={selectedGapId === candidate.gapId ? "candidate-card candidate-card-active" : "candidate-card"}
                  onClick={() => setSelectedGapId(candidate.gapId)}
                >
                  <div className="candidate-head">
                    <div>
                      <strong>{candidate.summary.slice(0, 88)}</strong>
                      <small>ID: {candidate.gapId}</small>
                    </div>
                  </div>
                  <p>{candidate.rationale || candidate.summary}</p>
                  <div className="candidate-bars">
                    <div className="mini-bar">
                      <span>Novelty</span>
                      <strong>{candidate.novelty ? `${(candidate.novelty / 5 * 100).toFixed(0)}%` : "-"}</strong>
                    </div>
                    <div className="mini-bar">
                      <span>Feasibility</span>
                      <strong>{feasibilityScore(candidate.feasibility) >= 3 ? "95%" : feasibilityScore(candidate.feasibility) >= 2 ? "75%" : "40%"}</strong>
                    </div>
                  </div>
                  {candidate.supportingPapers.length ? (
                    <div className="candidate-paper-count">📄 {candidate.supportingPapers.length} supporting papers</div>
                  ) : null}
                </button>
              ))
            ) : (
              <EmptyState title="No candidates yet" body="Wait for Human Select stage." />
            )}
          </div>
        </div>

        {/* Center Column: Discussion */}
        <div className="dashboard-col discussion-col">
          <div className="dashboard-col-head">
            <strong>Discussion</strong>
            <small>{selectedCandidate?.summary?.slice(0, 40) || "Select a direction"}</small>
          </div>
          <div className="discussion-panel macOS-chat">
            {selectedGapId && selectedCandidate ? (
              <div className="discussion-chat-shell">
                {shouldShowLoadAdvisorPrompt ? (
                  <div className="discussion-load-prompt">
                    <strong>顾问分析尚未加载</strong>
                    <button
                      className="button"
                      type="button"
                      onClick={() => void hydrateGap(selectedGapId)}
                      disabled={props.isBusy(`discuss-${selectedGapId}`)}
                    >
                      加载顾问分析
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="discussion-thread-shell">
                      <div className="discussion-thread">
                        {currentThread.length ? (
                          currentThread.map((message, index) => (
                            <div
                              key={`${message.role}-${message.message_id ?? index}`}
                              className={
                                message.role === "assistant"
                                  ? "chat-message chat-message-assistant"
                                  : "chat-message chat-message-user"
                              }
                            >
                              <div className="chat-avatar">{message.role === "assistant" ? "🤖" : "👤"}</div>
                              <div className="chat-message-body">
                                <p>{message.content}</p>
                                <span className="chat-time">{new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                              </div>
                            </div>
                          ))
                        ) : props.isBusy(`discuss-${selectedGapId}`) ? (
                          <EmptyState title="Loading Advisor" body="Gathering context..." />
                        ) : (
                          <EmptyState title="No discussion" body="Start a conversation about this direction." />
                        )}
                        <div ref={threadEndRef} />
                      </div>
                    </div>
                    <div className="discussion-composer-card">
                      <textarea
                        value={chatDraft}
                        onChange={(event) => setChatDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && !event.shiftKey) {
                            event.preventDefault();
                            void continueDiscussion();
                          }
                        }}
                        placeholder="Ask for changes..."
                      />
                      <button
                        className="button send-button"
                        type="button"
                        onClick={() => void continueDiscussion()}
                        disabled={!chatDraft.trim() || props.isBusy(`discuss-${selectedGapId}`)}
                      >
                        ↑
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <EmptyState title="Select a direction" body="Choose a candidate direction on the left to review it." />
            )}
          </div>
        </div>

        {/* Right Column: Activity */}
        <div className="dashboard-col activity-col">
          <div className="dashboard-col-head">
            <strong>Recent Activity</strong>
          </div>
          <div className="activity-feed">
            {recentTasks.length ? (
              recentTasks.map((task) => {
                const meta = taskMeta(task.kind);
                return (
                  <div key={task.task_id} className="activity-item">
                    <div className={`activity-dot ${task.status === "succeeded" ? "good" : task.status === "running" ? "warn" : "neutral"}`}></div>
                    <div className="activity-content">
                      <strong>{meta.label}</strong>
                      <p>{taskSummary(task)}</p>
                      <small>{task.created_at.replace("T", " ").slice(0, 16)}</small>
                    </div>
                  </div>
                );
              })
            ) : (
              <EmptyState title="No activity" body="Start a project to see activity here." />
            )}
            
            {/* Fallback to pilot form if no project */}
            {!props.selectedProject ? (
              <form
                className="pilot-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void props.startResearch({ researchGoal, projectName });
                }}
              >
                <label>
                  <span>Start New Research</span>
                  <textarea
                    value={researchGoal}
                    onChange={(event) => setResearchGoal(event.target.value)}
                    placeholder="E.g., Low-compute adversarial training"
                    required
                  />
                </label>
                <div className="pilot-actions">
                  <button className="button" type="submit" disabled={props.isBusy("guide-start")}>
                    Run Pipeline
                  </button>
                </div>
              </form>
            ) : attention.tone !== "normal" ? (
              <div className={`workspace-action-card ${attention.tone}`}>
                <strong>{attention.title}</strong>
                <p>{attention.body}</p>
                {attention.onAction ? (
                  <button className="button" type="button" onClick={attention.onAction}>{attention.actionLabel}</button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
"""

new_content = content[:start_idx] + new_return_block + content[end_idx:]

with open(r'c:\Anti Project\ResearchOS\frontend\src\components\OverviewTab.tsx', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("OverviewTab.tsx updated successfully.")
