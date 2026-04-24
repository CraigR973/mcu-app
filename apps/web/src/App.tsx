import { Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/context/theme'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'

function HomePage() {
  return (
    <main className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold tracking-tight">
            <span className="text-primary">MCU</span>
          </span>
          <span className="text-sm text-muted-foreground">Mark's Cinematic Universe</span>
        </div>
        <ThemeToggle />
      </header>

      <div className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
        <h1 className="text-4xl font-bold tracking-tight">
          Welcome to the <span className="text-primary">Real MCU</span>
        </h1>
        <p className="max-w-md text-muted-foreground">
          Mark's personal film universe — track every movie, rank every watch.
        </p>
        <div className="flex gap-3">
          <Button>Get Started</Button>
          <Button variant="outline">Learn More</Button>
        </div>
      </div>
    </main>
  )
}

function App() {
  return (
    <ThemeProvider>
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </ThemeProvider>
  )
}

export default App
