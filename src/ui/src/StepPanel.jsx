import { useState, useRef, useCallback } from 'react'

export default function StepPanel({ step }) {
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)
  const abortRef = useRef(null)

  const run = useCallback(async () => {
    setOutput('')
    setRunning(true)
    setActiveAgent(null)

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
                setOutput((prev) => prev + data.value)
              } else if (currentEvent === 'update' && data.agent) {
                setActiveAgent(data.agent)
              } else if (currentEvent === 'done') {
                // stream complete
              }
            } catch {
              // non-JSON data line, ignore
            }
            currentEvent = null
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setOutput((prev) => prev + `\n\nError: ${err.message}`)
      }
    } finally {
      setRunning(false)
      setActiveAgent(null)
      abortRef.current = null
    }
  }, [step])

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
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

      <pre className="min-h-[300px] max-h-[600px] overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-4 font-mono text-sm text-slate-800 shadow-inner">
        {output || (
          <span className="text-slate-400">
            Press &quot;Run Step {step}&quot; to start
          </span>
        )}
      </pre>
    </div>
  )
}
