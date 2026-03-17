import { useState } from 'react'
import { Loader2, Cpu, Scan, AlertCircle } from 'lucide-react'
import UploadZone from './components/UploadZone'
import PromptBuilder from './components/PromptBuilder'
import ResultsPanel from './components/ResultsPanel'
import { extractDocument } from './api/client'

const GLOBAL_STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Roboto+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html, body, #root {
    min-height: 100vh;
    background: #030712;
    color: #f1f5f9;
    font-family: Inter, sans-serif;
  }

  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: #030712; }
  ::-webkit-scrollbar-thumb { background: #1a2640; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #2d3f60; }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }

  @keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  @keyframes scanPulse {
    0%, 100% { opacity: 0.4; }
    50%       { opacity: 0.7; }
  }

  input:focus, textarea:focus, select:focus {
    outline: none !important;
    border-color: rgba(99,102,241,0.45) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.07) !important;
  }

  select option { background: #0a0f1e; color: #c8d5e8; }
`

function SectionLabel({ n, title, sub }) {
  return (
    <div style={{ marginBottom: '22px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
        <span style={{
          fontFamily: 'Roboto Mono, monospace',
          fontSize: '10px',
          color: '#6366f1',
          letterSpacing: '0.1em',
          fontWeight: 500,
        }}>
          {String(n).padStart(2, '0')}
        </span>
        <div style={{ flex: 1, height: '1px', background: 'linear-gradient(90deg, #1a2640 0%, transparent 100%)' }} />
      </div>
      <h2 style={{
        fontFamily: 'Inter, sans-serif',
        fontSize: '17px',
        fontWeight: 600,
        color: '#ffffff',
        letterSpacing: '-0.01em',
        marginBottom: sub ? '4px' : 0,
      }}>
        {title}
      </h2>
      {sub && (
        <p style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '12px',
          color: '#64748b',
        }}>
          {sub}
        </p>
      )}
    </div>
  )
}

export default function App() {
  const [file, setFile] = useState(null)
  const [prompts, setPrompts] = useState([])
  const [documentType, setDocumentType] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const isReady =
    file !== null &&
    prompts.length > 0 &&
    prompts.every(p => p.key.trim() !== '' && p.question.trim() !== '')

  const handleExtract = async () => {
    if (!isReady || loading) return
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const data = await extractDocument({ file, prompts, documentType })
      setResults(data)
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err.message ||
        'Extraction failed. Check that the backend is running.'
      )
    } finally {
      setLoading(false)
    }
  }

  const btnReady = isReady && !loading

  return (
    <>
      <style>{GLOBAL_STYLES}</style>

      <div style={{
        minHeight: '100vh',
        background: '#030712',
        backgroundImage: `
          radial-gradient(ellipse 90% 60% at 50% -10%, rgba(99,102,241,0.07) 0%, transparent 100%),
          radial-gradient(ellipse 40% 30% at 85% 80%, rgba(99,102,241,0.03) 0%, transparent 100%)
        `,
      }}>

        {/* ── Header ── */}
        <header style={{
          borderBottom: '1px solid #0d1422',
          padding: '14px 40px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          background: 'rgba(3,7,18,0.85)',
          backdropFilter: 'blur(10px)',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}>
          <div style={{
            width: 30,
            height: 30,
            borderRadius: '7px',
            background: 'rgba(99,102,241,0.12)',
            border: '1px solid rgba(99,102,241,0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Scan size={15} color="#818cf8" />
          </div>

          <div>
            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '13px',
              fontWeight: 600,
              color: '#ffffff',
            }}>
              local-ocr-idp
            </p>
            <p style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '11px',
              color: '#64748b',
              marginTop: '1px',
            }}>
              Ollama · FastAPI · local inference
            </p>
          </div>

          {/* Status dot */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: '#22c55e',
              boxShadow: '0 0 8px rgba(34,197,94,0.6)',
              animation: 'scanPulse 2.5s ease-in-out infinite',
            }} />
            <span style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '10px',
              color: '#64748b',
              letterSpacing: '0.05em',
            }}>
              LOCAL
            </span>
          </div>
        </header>

        {/* ── Main ── */}
        <main style={{
          maxWidth: '860px',
          margin: '0 auto',
          padding: '48px 24px 96px',
          display: 'flex',
          flexDirection: 'column',
          gap: '52px',
        }}>

          {/* Section 1 — Upload */}
          <section>
            <SectionLabel n={1} title="Document" sub="PDF · PNG · JPG · WEBP" />
            <UploadZone file={file} onFileChange={setFile} />
          </section>

          {/* Section 2 — Prompts */}
          <section>
            <SectionLabel
              n={2}
              title="Extraction Prompts"
              sub="Define what to extract — each prompt maps to one output field"
            />
            <PromptBuilder
              prompts={prompts}
              setPrompts={setPrompts}
              documentType={documentType}
              setDocumentType={setDocumentType}
            />
          </section>

          {/* Run button + error */}
          <div>
            {error && (
              <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                background: 'rgba(239,68,68,0.06)',
                border: '1px solid rgba(239,68,68,0.2)',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '14px',
                animation: 'fadeSlideIn 0.2s ease',
              }}>
                <AlertCircle size={14} color="#f87171" style={{ marginTop: '1px', flexShrink: 0 }} />
                <span style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '13px',
                  color: '#fca5a5',
                  lineHeight: 1.55,
                }}>
                  {error}
                </span>
              </div>
            )}

            <button
              onClick={handleExtract}
              disabled={!isReady || loading}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: '8px',
                border: `1px solid ${btnReady ? 'rgba(99,102,241,0.35)' : '#1a2640'}`,
                background: btnReady
                  ? 'rgba(99,102,241,0.1)'
                  : '#08111e',
                color: btnReady ? '#a5b4fc' : '#334155',
                fontSize: '14px',
                fontFamily: 'Inter, sans-serif',
                fontWeight: 500,
                cursor: btnReady ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'all 0.2s',
                letterSpacing: '0.06em',
                boxShadow: btnReady ? '0 0 24px rgba(99,102,241,0.08)' : 'none',
              }}
            >
              {loading ? (
                <>
                  <Loader2 size={14} style={{ animation: 'spin 0.75s linear infinite' }} />
                  Extracting...
                </>
              ) : (
                <>
                  <Cpu size={14} />
                  Run Extraction
                </>
              )}
            </button>
          </div>

          {/* Section 3 — Results */}
          {results && (
            <section style={{ animation: 'fadeSlideIn 0.35s ease' }}>
              <SectionLabel
                n={3}
                title="Extraction Results"
                sub={`${results.successful_extractions} of ${results.total_prompts} fields extracted`}
              />
              <ResultsPanel data={results} />
            </section>
          )}

        </main>
      </div>
    </>
  )
}
