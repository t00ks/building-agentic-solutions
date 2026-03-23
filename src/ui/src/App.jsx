import { useState, useEffect } from 'react'
import StepPanel from './StepPanel'

const STEPS = [1, 2, 3, 4, 5]

const STEP_LABELS = {
  1: 'Agent + 1 Tool',
  2: 'Agents + Tools (MCP & Streaming)',
  3: 'Multi-Agent',
  4: 'Supervisor',
  5: 'Full Orchestration',
}

function App() {
  const [activeStep, setActiveStep] = useState(1)
  const [dark, setDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') === 'dark' ||
        (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)
    }
    return false
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50 dark:bg-slate-900">
      <header className="shrink-0 border-b border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            Agentic Framework Demo
          </h1>
          <button
            onClick={() => setDark(!dark)}
            className="rounded-md border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600"
            aria-label="Toggle dark mode"
          >
            {dark ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>

      <main className="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col px-4 py-6">
        {/* Tabs */}
        <nav className="mb-4 flex shrink-0 gap-1 rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-800">
          {STEPS.map((step) => (
            <button
              key={step}
              onClick={() => setActiveStep(step)}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                activeStep === step
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700'
              }`}
            >
              Step {step}
              <span className="ml-1 hidden text-xs opacity-75 sm:inline">
                — {STEP_LABELS[step]}
              </span>
            </button>
          ))}
        </nav>

        {/* Panel */}
        <div className="min-h-0 flex-1">
          {STEPS.map((step) => (
            <div
              key={step}
              className={`h-full ${activeStep === step ? '' : 'hidden'}`}
            >
              <StepPanel step={step} />
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}

export default App
