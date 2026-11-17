import React from 'react'
import ReactDOM from 'react-dom/client'
import { enableMapSet } from 'immer'
import App from './App'
import './index.css'

// Enable Map/Set plugin in Immer so Zustand state with Sets works seamlessly
enableMapSet()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
