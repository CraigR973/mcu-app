import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/button'

export default function UnauthorizedPage() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="text-center space-y-4">
        <h1 className="text-2xl font-bold text-foreground">Access denied</h1>
        <p className="text-sm text-muted-foreground">You don't have permission to view this page.</p>
        <Button onClick={() => navigate('/')}>Go home</Button>
      </div>
    </div>
  )
}
