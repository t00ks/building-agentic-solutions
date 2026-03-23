import { useState, useRef, useCallback } from 'react'

const SUPERVISOR = 'trip_supervisor'

function isSupervisor(agent) {
  return agent && agent.toLowerCase().includes('supervisor')
}

function AgentCard({ agent, content }) {
  let parsed = null
  try {
    parsed = JSON.parse(content)
  } catch {
    // not valid JSON — render raw
  }

  if (!parsed) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h4 className="mb-2 text-sm font-semibold text-slate-700">{agent}</h4>
        <pre className="whitespace-pre-wrap text-sm text-slate-600">
          {content}
        </pre>
      </div>
    )
  }

  const { agent: _a, ...rest } = parsed
  const entries = Object.entries(rest)

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
        <span className="inline-block rounded bg-indigo-600 px-2 py-0.5 text-xs font-semibold text-white">
          {agent}
        </span>
      </h4>
      <div className="space-y-3">
        {entries.map(([key, value]) => (
          <AgentField key={key} label={key} value={value} />
        ))}
      </div>
    </div>
  )
}

function AgentField({ label, value }) {
  const title = label.replace(/_/g, ' ')

  if (value === null || value === undefined) return null

  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return (
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
          {title}
        </dt>
        <dd className="mt-0.5 text-sm text-slate-700">{String(value)}</dd>
      </div>
    )
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return null
    if (typeof value[0] === 'string') {
      return (
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
            {title}
          </dt>
          <dd className="mt-1">
            <ul className="list-inside list-disc space-y-0.5 text-sm text-slate-700">
              {value.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          </dd>
        </div>
      )
    }
    // array of objects
    return (
      <div>
        <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
          {title}
        </dt>
        <dd className="space-y-2">
          {value.map((item, i) => (
            <div
              key={i}
              className="rounded border border-slate-100 bg-slate-50 p-2"
            >
              {typeof item === 'object' && item !== null ? (
                <div className="space-y-1">
                  {Object.entries(item).map(([k, v]) => (
                    <div key={k} className="flex gap-2 text-xs">
                      <span className="font-medium text-slate-500">
                        {k.replace(/_/g, ' ')}:
                      </span>
                      <span className="text-slate-700">
                        {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-sm text-slate-700">
                  {JSON.stringify(item)}
                </span>
              )}
            </div>
          ))}
        </dd>
      </div>
    )
  }

  if (typeof value === 'object') {
    return (
      <div>
        <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
          {title}
        </dt>
        <dd className="rounded border border-slate-100 bg-slate-50 p-2">
          <div className="space-y-1">
            {Object.entries(value).map(([k, v]) => (
              <div key={k} className="flex gap-2 text-xs">
                <span className="font-medium text-slate-500">
                  {k.replace(/_/g, ' ')}:
                </span>
                <span className="text-slate-700">
                  {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                </span>
              </div>
            ))}
          </div>
        </dd>
      </div>
    )
  }

  return null
}

export default function StepPanel({ step }) {
  const [output, setOutput] = useState('')
  const [agentOutputs, setAgentOutputs] = useState([])
  const [toolCalls, setToolCalls] = useState([])
  const [running, setRunning] = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)
  const abortRef = useRef(null)
  const agentBufferRef = useRef({ agent: null, chunks: [] })

  const flushAgentBuffer = useCallback(() => {
    const { agent, chunks } = agentBufferRef.current
    if (agent && chunks.length > 0 && !isSupervisor(agent)) {
      const content = chunks.join('')
      setAgentOutputs((prev) => [{ agent, content }, ...prev])
    }
    agentBufferRef.current = { agent: null, chunks: [] }
  }, [])

  const run = useCallback(async () => {
    setOutput('')
    setAgentOutputs([])
    setToolCalls([])
    setRunning(true)
    setActiveAgent(null)
    agentBufferRef.current = { agent: null, chunks: [] }

    if (step === 1) {
      try {
        const res = await fetch(`/step1`)
        const messages = await res.json()
        const text = messages
          .map((m) => {
            const role = m.type ?? m.role ?? 'unknown'
            const content =
              typeof m.content === 'string'
                ? m.content
                : JSON.stringify(m.content, null, 2)
            return `[${role}]\n${content}`
          })
          .join('\n\n---\n\n')
        setOutput(text)
      } catch (err) {
        setOutput(`Error: ${err.message}`)
      } finally {
        setRunning(false)
      }
      return
    }

    // Steps 2-5: SSE stream
    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const res = await fetch(`/step${step}`, { signal: ctrl.signal })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // keep incomplete line in buffer

        let currentEvent = null
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7)
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              if (currentEvent === 'response' && data.value) {
                const currentAgent = agentBufferRef.current.agent
                if (isSupervisor(currentAgent)) {
                  setOutput((prev) => prev + data.value)
                } else {
                  agentBufferRef.current.chunks.push(data.value)
                }
              } else if (currentEvent === 'update' && data.agent) {
                flushAgentBuffer()
                agentBufferRef.current = { agent: data.agent, chunks: [] }
                setActiveAgent(data.agent)
              } else if (currentEvent === 'debug' && data.tool_name) {
                setToolCalls((prev) => [...prev, data])
              } else if (currentEvent === 'done') {
                flushAgentBuffer()
              }
            } catch {
              // non-JSON data line, ignore
            }
            currentEvent = null
          }
        }
      }
      // flush anything remaining when stream ends
      flushAgentBuffer()
    } catch (err) {
      if (err.name !== 'AbortError') {
        setOutput((prev) => prev + `\n\nError: ${err.message}`)
      }
    } finally {
      setRunning(false)
      setActiveAgent(null)
      abortRef.current = null
    }
  }, [step, flushAgentBuffer])

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const showToolPanel = step >= 2

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex shrink-0 items-center gap-3">
        <button
          onClick={running ? stop : run}
          className={`rounded-md px-4 py-2 text-sm font-medium text-white transition-colors ${
            running
              ? 'bg-red-600 hover:bg-red-700'
              : 'bg-indigo-600 hover:bg-indigo-700'
          }`}
        >
          {running ? 'Stop' : `Run Step ${step}`}
        </button>

        {running && (
          <span className="flex items-center gap-2 text-sm text-slate-500">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-green-500" />
            {activeAgent ? `Agent: ${activeAgent}` : 'Streaming…'}
          </span>
        )}
      </div>

      {showToolPanel ? (
        <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
          {/* Left column: supervisor output + agent cards */}
          <div className="flex min-h-0 flex-col gap-1">
            <h3 className="shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Output
            </h3>
            <div className="min-h-0 flex-1 space-y-3 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3">

            {/* Supervisor streamed output (always on top when active) */}
            {output && (
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <span className="inline-block rounded bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
                    Trip Supervisor
                  </span>
                </h4>
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                  {output}
                </div>
              </div>
            )}

            {/* Buffering indicator for non-supervisor agent */}
            {running && activeAgent && !isSupervisor(activeAgent) && (
              <div className="flex items-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-sm text-slate-500">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-400" />
                <span className="font-medium">{activeAgent}</span> is working…
              </div>
            )}

            {/* Agent result cards (newest first) */}
            {agentOutputs.map((ao, i) => (
              <AgentCard key={i} agent={ao.agent} content={ao.content} />
            ))}

            {!output && agentOutputs.length === 0 && !running && (
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <span className="text-sm text-slate-400">
                  Press &quot;Run Step {step}&quot; to start
                </span>
              </div>
            )}
            </div>
          </div>

          {/* Right column: tool calls */}
          <div className="flex min-h-0 flex-col gap-1">
            <h3 className="shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Tool Calls
            </h3>
            <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-4 shadow-inner">
              {toolCalls.length === 0 ? (
                <span className="text-sm text-slate-500">
                  No tool calls yet
                </span>
              ) : (
                <div className="flex flex-col gap-3">
                  {toolCalls.map((tc, i) => (
                    <div
                      key={i}
                      className="rounded-md border border-slate-700 bg-slate-800 p-3"
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <span className="inline-block rounded bg-indigo-600 px-2 py-0.5 text-xs font-semibold text-white">
                          {tc.tool_name}
                        </span>
                        <span className="text-xs text-slate-500">
                          #{i + 1}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {tc.tool_data.map((d, j) => {
                          try {
                            const parsed = JSON.parse(d)
                            return (
                              <pre
                                key={j}
                                className="whitespace-pre-wrap rounded bg-slate-950 p-2 font-mono text-xs text-emerald-400"
                              >
                                {JSON.stringify(parsed, null, 2)}
                              </pre>
                            )
                          } catch {
                            return (
                              <pre
                                key={j}
                                className="whitespace-pre-wrap rounded bg-slate-950 p-2 font-mono text-xs text-slate-300"
                              >
                                {d}
                              </pre>
                            )
                          }
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Step 1: single output panel */
        <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-4 font-mono text-sm text-slate-800 shadow-inner">
          {output || (
            <span className="text-slate-400">
              Press &quot;Run Step {step}&quot; to start
            </span>
          )}
        </pre>
      )}
    </div>
  )
}
