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
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-4 py-4">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            Agentic Framework Demo
          </h1>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        {/* Tabs */}
        <nav className="mb-6 flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
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
        <StepPanel key={activeStep} step={activeStep} />
      </main>
    </div>
  )
}

export default App
