import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button } from './ui/button'
import {
  OUT_OF_DATE,
  describeError,
  isChunkFailure,
  reloadOnceForNewBuild,
} from '@/lib/describe-error'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
    // A lazy route whose chunk a deploy removed: "Try again" would fail the same way until
    // a full reload, so reload once (Batch X8).
    if (isChunkFailure(error)) reloadOnceForNewBuild()
  }

  reset = () => this.setState({ hasError: false, error: null })

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
          <div className="text-center space-y-4 max-w-md px-4">
            <h1 className="text-2xl font-bold">Something went wrong</h1>
            <p className="text-muted-foreground text-sm">
              {describeError(this.state.error, 'An unexpected error occurred.')}
            </p>
            {describeError(this.state.error, '') === OUT_OF_DATE ? (
              <Button onClick={() => window.location.reload()}>Reload</Button>
            ) : (
              <Button onClick={this.reset}>Try again</Button>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
