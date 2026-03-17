import { FileText, Hash, ListChecks, CheckCircle2 } from 'lucide-react'

const CONFIDENCE = {
  high:      { bg: 'rgba(34,197,94,0.08)',  border: 'rgba(34,197,94,0.2)',  color: '#4ade80', label: 'HIGH' },
  medium:    { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', color: '#fbbf24', label: 'MED'  },
  low:       { bg: 'rgba(249,115,22,0.08)', border: 'rgba(249,115,22,0.2)', color: '#fb923c', label: 'LOW'  },
  not_found: { bg: 'rgba(75,85,99,0.08)',   border: 'rgba(75,85,99,0.2)',   color: '#6b7280', label: 'N/F'  },
}

function ConfidenceBadge({ confidence }) {
  const s = CONFIDENCE[confidence] ?? CONFIDENCE.not_found
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      background: s.bg,
      border: `1px solid ${s.border}`,
      borderRadius: '4px',
      padding: '2px 7px',
      fontSize: '10px',
      fontFamily: 'Roboto Mono, monospace',
      color: s.color,
      letterSpacing: '0.08em',
      fontWeight: 500,
      flexShrink: 0,
    }}>
      {s.label}
    </span>
  )
}

function StatPill({ icon: Icon, label, value }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
      background: '#0a0f1e',
      border: '1px solid #1a2640',
      borderRadius: '8px',
      padding: '14px 18px',
      flex: 1,
      minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Icon size={12} color="#3d5070" />
        <span style={{
          fontSize: '10px',
          fontFamily: 'Roboto Mono, monospace',
          color: '#64748b',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {label}
        </span>
      </div>
      <span style={{
        fontSize: '20px',
        fontFamily: 'Roboto Mono, monospace',
        color: '#ffffff',
        fontWeight: 600,
        lineHeight: 1.2,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {value ?? '—'}
      </span>
    </div>
  )
}

function ResultCard({ result, index }) {
  const isNull = result.value === null || result.value === undefined
  const isArray = !isNull && Array.isArray(result.value)
  const isObject = !isNull && !isArray && typeof result.value === 'object'

  return (
    <div style={{
      background: '#0a0f1e',
      border: '1px solid #1a2640',
      borderRadius: '8px',
      padding: '18px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      animation: 'fadeSlideIn 0.3s ease both',
      animationDelay: `${index * 40}ms`,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span style={{
            fontFamily: 'Roboto Mono, monospace',
            color: '#818cf8',
            fontSize: '13px',
            fontWeight: 500,
          }}>
            {result.key}
          </span>
          <span style={{
            fontSize: '12px',
            color: '#94a3b8',
            fontFamily: 'Inter, sans-serif',
            lineHeight: 1.45,
          }}>
            {result.question}
          </span>
        </div>
        <ConfidenceBadge confidence={result.confidence} />
      </div>

      {/* Value */}
      <div style={{ borderTop: '1px solid #0d1422', paddingTop: '12px' }}>
        {isNull ? (
          <span style={{ color: '#475569', fontFamily: 'Roboto Mono, monospace', fontSize: '14px' }}>
            —
          </span>
        ) : (isArray || isObject) ? (
          <pre style={{
            margin: 0,
            fontFamily: 'Roboto Mono, monospace',
            fontSize: '11px',
            color: '#cbd5e1',
            background: '#020710',
            border: '1px solid #0d1422',
            borderRadius: '6px',
            padding: '12px 14px',
            overflowX: 'auto',
            lineHeight: 1.65,
            maxHeight: '280px',
            overflowY: 'auto',
          }}>
            {JSON.stringify(result.value, null, 2)}
          </pre>
        ) : (
          <span style={{
            color: '#f1f5f9',
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            lineHeight: 1.55,
          }}>
            {String(result.value)}
          </span>
        )}
      </div>
    </div>
  )
}

export default function ResultsPanel({ data }) {
  return (
    <div>
      {/* Summary bar */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <StatPill icon={FileText}     label="Doc type"  value={data.document_type} />
        <StatPill icon={Hash}         label="Pages"     value={data.total_pages} />
        <StatPill icon={ListChecks}   label="Prompts"   value={data.total_prompts} />
        <StatPill icon={CheckCircle2} label="Extracted" value={data.successful_extractions} />
      </div>

      {/* Cards grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: '12px',
      }}>
        {data.results?.map((result, i) => (
          <ResultCard key={result.key ?? i} result={result} index={i} />
        ))}
      </div>
    </div>
  )
}
