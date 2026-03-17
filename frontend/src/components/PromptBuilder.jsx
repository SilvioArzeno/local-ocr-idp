import { useState } from 'react'
import { Plus, Trash2, Zap } from 'lucide-react'

const DEFAULT_PROMPTS = [
  {
    key: 'patient_name',
    question: 'What is the full name of the patient?',
    type: 'string',
    required: true,
  },
  {
    key: 'date_of_birth',
    question: 'What is the patient date of birth?',
    type: 'date',
    required: true,
  },
  {
    key: 'collected_date',
    question: 'What is the date the specimen was collected or what is the collected date?',
    type: 'date',
    required: true,
  },
  {
    key: 'test_results',
    question:
      `This is a Lab diagnostics test with multiple blood work values, return a json with as many extracted values as possible using ONLY these acronyms (And for the corresponding test) :


WBC - White Blood Cell
RBC - Red Blood Cell
Platelets - Platelets
HGB - Hemogoblin
NA - Sodium
Creat - Creatinine
K - Potassium
AST - Aspartate Aminotransferase
ALT - Alanine Aminotransferase
PT - Prothrombin Time
PTT - Partial Thromboplastin Time
INR - International Normalized Ratio
Glucose - Glucose
HbA1C - Hemoglobin A1C
T3 - T3 (Thyroids)
T4 - T4 (Thyroids)
TSH - TSH (Thyroids)
HIV - Hiv Test or Viral Load
CD4 - CD4 Count
BHCG - bHCG (Pregnancy Test)
HepC - Hepatitis C

If you can't find a value for any of these do not include them in the json.`,
    type: 'array',
    required: true,
  },
]

const TYPE_OPTIONS = ['string', 'number', 'date', 'array', 'boolean']

function newPrompt() {
  return { id: crypto.randomUUID(), key: '', question: '', type: 'string', required: false }
}

const baseInputStyle = {
  background: '#0d1526',
  border: '1px solid #1e2d45',
  borderRadius: '6px',
  color: '#f1f5f9',
  fontSize: '13px',
  fontFamily: 'Inter, sans-serif',
  padding: '7px 10px',
  width: '100%',
  boxSizing: 'border-box',
}

function PromptRow({ prompt, onChange, onDelete }) {
  const [hoverDelete, setHoverDelete] = useState(false)

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '140px 1fr 90px 44px 34px',
      gap: '8px',
      alignItems: 'start',
    }}>
      <input
        value={prompt.key}
        onChange={e => onChange('key', e.target.value)}
        placeholder="field_key"
        spellCheck={false}
        style={{
          ...baseInputStyle,
          color: prompt.key ? '#a5b4fc' : '#475569',
          fontFamily: 'Roboto Mono, monospace',
          fontSize: '12px',
        }}
      />
      <textarea
        value={prompt.question}
        onChange={e => onChange('question', e.target.value)}
        placeholder="Ask a question about the document..."
        rows={2}
        style={{
          ...baseInputStyle,
          resize: 'vertical',
          minHeight: '36px',
          lineHeight: '1.45',
        }}
      />
      <select
        value={prompt.type}
        onChange={e => onChange('type', e.target.value)}
        style={{ ...baseInputStyle, cursor: 'pointer' }}
      >
        {TYPE_OPTIONS.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        paddingTop: '9px',
      }}>
        <input
          type="checkbox"
          checked={prompt.required}
          onChange={e => onChange('required', e.target.checked)}
          style={{ width: '14px', height: '14px', cursor: 'pointer', accentColor: '#6366f1' }}
        />
      </div>

      <button
        onClick={onDelete}
        onMouseEnter={() => setHoverDelete(true)}
        onMouseLeave={() => setHoverDelete(false)}
        title="Delete prompt"
        style={{
          background: hoverDelete ? 'rgba(239,68,68,0.08)' : 'transparent',
          border: `1px solid ${hoverDelete ? 'rgba(239,68,68,0.25)' : '#1a2640'}`,
          borderRadius: '6px',
          padding: '7px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: hoverDelete ? '#f87171' : '#64748b',
          transition: 'all 0.15s',
        }}
      >
        <Trash2 size={12} />
      </button>
    </div>
  )
}

export default function PromptBuilder({ prompts, setPrompts, documentType, setDocumentType }) {
  const [hoverAdd, setHoverAdd] = useState(false)
  const [hoverDefaults, setHoverDefaults] = useState(false)

  const loadDefaults = () => {
    setDocumentType('lab_report')
    setPrompts(DEFAULT_PROMPTS.map(p => ({ ...p, id: crypto.randomUUID() })))
  }

  const addPrompt = () => {
    setPrompts(prev => [...prev, newPrompt()])
  }

  const updatePrompt = (id, field, value) => {
    setPrompts(prev => prev.map(p => p.id === id ? { ...p, [field]: value } : p))
  }

  const deletePrompt = (id) => {
    setPrompts(prev => prev.filter(p => p.id !== id))
  }

  return (
    <div>
      {/* Document type + defaults */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '24px', alignItems: 'flex-end' }}>
        <div style={{ flex: 1 }}>
          <label style={{
            display: 'block',
            fontSize: '10px',
            fontFamily: 'Inter, sans-serif',
            color: '#64748b',
            marginBottom: '6px',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
          }}>
            Document Type
          </label>
          <input
            value={documentType}
            onChange={e => setDocumentType(e.target.value)}
            placeholder="e.g. lab_report, invoice, contract"
            spellCheck={false}
            style={{ ...baseInputStyle, fontSize: '13px' }}
          />
        </div>

        <button
          onClick={loadDefaults}
          onMouseEnter={() => setHoverDefaults(true)}
          onMouseLeave={() => setHoverDefaults(false)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: hoverDefaults ? 'rgba(99,102,241,0.12)' : 'rgba(99,102,241,0.06)',
            border: '1px solid rgba(99,102,241,0.25)',
            borderRadius: '6px',
            color: '#818cf8',
            fontSize: '12px',
            fontFamily: 'Inter, sans-serif',
            padding: '8px 13px',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            transition: 'background 0.15s',
            flexShrink: 0,
          }}
        >
          <Zap size={12} />
          Lab defaults
        </button>
      </div>

      {/* Column headers */}
      {prompts.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '140px 1fr 90px 44px 34px',
          gap: '8px',
          paddingBottom: '8px',
          borderBottom: '1px solid #0d1422',
          marginBottom: '10px',
        }}>
          {['Key', 'Question', 'Type', 'Req', ''].map((h, i) => (
            <span key={i} style={{
              fontSize: '10px',
              fontFamily: 'Inter, sans-serif',
              color: '#64748b',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
            }}>
              {h}
            </span>
          ))}
        </div>
      )}

      {/* Rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {prompts.map(p => (
          <PromptRow
            key={p.id}
            prompt={p}
            onChange={(field, value) => updatePrompt(p.id, field, value)}
            onDelete={() => deletePrompt(p.id)}
          />
        ))}
      </div>

      {/* Add row button */}
      <button
        onClick={addPrompt}
        onMouseEnter={() => setHoverAdd(true)}
        onMouseLeave={() => setHoverAdd(false)}
        style={{
          marginTop: prompts.length > 0 ? '10px' : '0',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'transparent',
          border: `1px dashed ${hoverAdd ? '#2d3f60' : '#1a2640'}`,
          borderRadius: '6px',
          color: hoverAdd ? '#94a3b8' : '#64748b',
          fontSize: '12px',
          fontFamily: 'Inter, sans-serif',
          padding: '9px 14px',
          cursor: 'pointer',
          width: '100%',
          justifyContent: 'center',
          transition: 'all 0.15s',
        }}
      >
        <Plus size={12} />
        Add prompt
      </button>
    </div>
  )
}
