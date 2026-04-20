import { Routes, Route } from 'react-router-dom'

function App() {
  return (
    <Routes>
      <Route path="/" element={<div className="p-8 text-2xl font-bold">MCU — Mark's Cinematic Universe</div>} />
    </Routes>
  )
}

export default App
