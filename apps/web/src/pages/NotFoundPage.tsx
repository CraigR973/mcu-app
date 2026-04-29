import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/button'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
      <div className="text-center space-y-4 px-4">
        <p className="text-8xl font-bold text-primary">404</p>
        <h1 className="text-2xl font-bold">Page not found</h1>
        <p className="text-muted-foreground">That page doesn't exist in this universe.</p>
        <Button onClick={() => navigate('/')}>Go home</Button>
      </div>
    </div>
  )
}
