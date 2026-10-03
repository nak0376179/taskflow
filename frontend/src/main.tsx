import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

const theme = createTheme({
  cssVariables: { colorSchemeSelector: 'class' },
  colorSchemes: {
    light: { palette: { primary: { main: '#3f51b5' }, background: { default: '#f4f5f9' } } },
    dark: { palette: { primary: { main: '#8c9eff' } } },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: '"Inter", "Noto Sans JP", system-ui, -apple-system, "Segoe UI", sans-serif',
  },
})

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5_000 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={theme} defaultMode="system">
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
