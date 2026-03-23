import { useState } from 'react'

const STEP_CONFIGS = {
  1: {
    type: 'single',
    agent: { name: 'ItineraryAgent', tools: ['place_info_tool'] },
  },
  2: {
    type: 'single',
    agent: {
      name: 'itinerary_agent',
      tools: [
        'place_info_tool',
        'transit_time_tool',
        'budget_estimator_tool',
        'weather_tool',
      ],
    },
  },
  3: {
    type: 'chain',
    agents: [
      {
        name: 'itinerary_agent',
        tools: ['place_info_tool', 'transit_time_tool', 'weather_tool'],
      },
      {
        name: 'local_info_agent',
        tools: ['local_events_tool', 'currency_tool', 'budget_estimator_tool'],
      },
      {
        name: 'booking_agent',
        tools: ['hotel_search_tool', 'flight_search_tool'],
      },
    ],
  },
  4: {
    type: 'supervisor',
    supervisor: { name: 'trip_supervisor', tools: ['validator_tool'] },
    children: [
      {
        name: 'itinerary_agent',
        tools: ['place_info_tool', 'transit_time_tool', 'weather_tool'],
      },
      {
        name: 'booking_agent',
        tools: ['hotel_search_tool', 'flight_search_tool'],
      },
      {
        name: 'local_info_agent',
        tools: ['local_events_tool', 'currency_tool', 'budget_estimator_tool'],
      },
    ],
  },
  5: {
    type: 'supervisor',
    supervisor: {
      name: 'trip_supervisor',
      tools: ['validator_tool', 'write_up_tool'],
    },
    children: [
      {
        name: 'itinerary_agent',
        tools: [
          'place_info_tool',
          'transit_time_tool',
          'weather_tool',
          'map_route_tool',
        ],
      },
      {
        name: 'booking_agent',
        tools: [
          'flight_search_tool',
          'hotel_search_tool',
          'restaurant_search_tool',
          'booking_api_simulator',
        ],
      },
      {
        name: 'local_info_agent',
        tools: [
          'local_events_tool',
          'restaurant_search_tool',
          'user_pref_store',
          'emergency_info_tool',
        ],
      },
      {
        name: 'budget_agent',
        tools: ['budget_estimator_tool', 'currency_tool'],
      },
    ],
  },
}

function AgentNode({ name, tools, variant = 'agent' }) {
  const colors =
    variant === 'supervisor'
      ? 'border-emerald-200 bg-emerald-50'
      : 'border-indigo-200 bg-indigo-50'
  const badgeColor =
    variant === 'supervisor' ? 'bg-emerald-600' : 'bg-indigo-600'

  return (
    <div
      className={`flex flex-col items-center gap-1.5 rounded-lg border ${colors} px-3 py-2`}
    >
      <span
        className={`whitespace-nowrap rounded px-2 py-0.5 text-[11px] font-semibold text-white ${badgeColor}`}
      >
        {name.replace(/_/g, ' ')}
      </span>
      {tools.length > 0 && (
        <div className="flex flex-wrap justify-center gap-1">
          {tools.map((tool) => (
            <span
              key={tool}
              className="whitespace-nowrap rounded bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500 ring-1 ring-slate-200"
            >
              {tool}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function HArrow() {
  return (
    <div className="flex shrink-0 items-center px-1">
      <div className="h-px w-4 bg-slate-300" />
      <div className="h-0 w-0 border-y-[3px] border-l-[5px] border-y-transparent border-l-slate-300" />
    </div>
  )
}

function QueryNode() {
  return (
    <div className="shrink-0 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-500">
      User Query
    </div>
  )
}

function SingleDiagram({ config }) {
  return (
    <div className="flex items-center justify-center">
      <QueryNode />
      <HArrow />
      <AgentNode name={config.agent.name} tools={config.agent.tools} />
    </div>
  )
}

function ChainDiagram({ config }) {
  return (
    <div className="flex items-start justify-center">
      <div className="mt-3">
        <QueryNode />
      </div>
      {config.agents.map((agent, i) => (
        <div key={i} className="flex items-start">
          <div className="mt-3">
            <HArrow />
          </div>
          <AgentNode name={agent.name} tools={agent.tools} />
        </div>
      ))}
    </div>
  )
}

function SupervisorDiagram({ config }) {
  const { supervisor, children } = config

  return (
    <div className="flex flex-col items-center">
      {/* User query → supervisor */}
      <div className="flex items-center">
        <QueryNode />
        <HArrow />
        <AgentNode
          name={supervisor.name}
          tools={supervisor.tools}
          variant="supervisor"
        />
      </div>

      {/* Vertical connector from supervisor down to rail */}
      <div className="h-5 w-px bg-slate-300" />

      {/* Children with tree connectors */}
      <div className="flex">
        {children.map((child, i, arr) => (
          <div key={i} className="flex flex-col items-center px-2">
            {/* Tree connector: left-rail | vertical-drop | right-rail */}
            <div className="flex h-5 w-full items-start">
              <div
                className={`h-px flex-1 ${i > 0 ? 'bg-slate-300' : ''}`}
              />
              <div className="h-full w-px shrink-0 bg-slate-300" />
              <div
                className={`h-px flex-1 ${i < arr.length - 1 ? 'bg-slate-300' : ''}`}
              />
            </div>
            <AgentNode name={child.name} tools={child.tools} />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function AgentDiagram({ step }) {
  const [open, setOpen] = useState(true)
  const config = STEP_CONFIGS[step]
  if (!config) return null

  return (
    <div className="shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700"
      >
        <span
          className={`inline-block text-[10px] transition-transform ${open ? 'rotate-90' : ''}`}
        >
          ▶
        </span>
        Architecture
      </button>
      {open && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white px-4 py-3">
          {config.type === 'single' && <SingleDiagram config={config} />}
          {config.type === 'chain' && <ChainDiagram config={config} />}
          {config.type === 'supervisor' && (
            <SupervisorDiagram config={config} />
          )}
        </div>
      )}
    </div>
  )
}
