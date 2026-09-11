import { useEffect, useState } from 'react'
import './App.css'

type HealthResponse = {
  status: string
  service: string
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: HealthResponse) => {
        setHealth(data)
        setError(null)
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : String(e))
        setHealth(null)
      })
  }, [])

  return (
    <main>
      <h1>tiered-homework frontend</h1>
      <section>
        <h2>Backend /health</h2>
        {health ? (
          <pre data-testid="health-ok">
            status: {health.status}
            {'\n'}service: {health.service}
          </pre>
        ) : (
          <pre data-testid="health-err">error: {error ?? 'loading...'}</pre>
        )}
      </section>
    </main>
  )
}

export default App