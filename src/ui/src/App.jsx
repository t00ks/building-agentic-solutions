import { useState } from 'react'
import StepPanel from './StepPanel'

const STEPS = [1, 2, 3, 4, 5]

const STEP_LABELS = {
  1: 'Single Agent',
  2: 'Agent + Tools',
  3: 'Multi-Agent',
  4: 'Supervisor',
  5: 'Full Orchestration',
}

function App() {
  const [activeStep, setActiveStep] = useState(1)

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      <header className="shrink-0 border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            Agentic Framework Demo
          </h1>
        </div>
      </header>

      <main className="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col px-4 py-6">
        {/* Tabs */}
        <nav className="mb-4 flex shrink-0 gap-1 rounded-lg border border-slate-200 bg-white p-1">
          {STEPS.map((step) => (
            <button
              key={step}
              onClick={() => setActiveStep(step)}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                activeStep === step
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100'
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
