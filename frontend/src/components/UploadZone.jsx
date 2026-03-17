import { useState, useRef, useCallback } from 'react'
import { Upload, FileText, Image, X } from 'lucide-react'

const ACCEPTED_TYPES = {
  'application/pdf': 'PDF',
  'image/png': 'PNG',
  'image/jpeg': 'JPG',
  'image/webp': 'WEBP',
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

export default function UploadZone({ file, onFileChange }) {
  const [isDragging, setIsDragging] = useState(false)
  const [hoverRemove, setHoverRemove] = useState(false)
  const inputRef = useRef(null)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped && ACCEPTED_TYPES[dropped.type]) {
      onFileChange(dropped)
    }
  }, [onFileChange])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false)
    }
  }, [])

  const handleInputChange = (e) => {
    const selected = e.target.files[0]
    if (selected) onFileChange(selected)
    e.target.value = ''
  }

  const isPDF = file?.type === 'application/pdf'
  const fileTypeLabel = file ? (ACCEPTED_TYPES[file.type] || 'FILE') : null

  if (file) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
        background: '#0a0f1e',
        border: '1px solid #1a2640',
        borderRadius: '8px',
        padding: '14px 18px',
      }}>
        <div style={{
          width: 38,
          height: 38,
          borderRadius: '8px',
          background: isPDF ? 'rgba(99,102,241,0.1)' : 'rgba(34,197,94,0.08)',
          border: `1px solid ${isPDF ? 'rgba(99,102,241,0.25)' : 'rgba(34,197,94,0.2)'}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          {isPDF
            ? <FileText size={17} color="#818cf8" />
            : <Image size={17} color="#4ade80" />
          }
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: 0,
            color: '#f1f5f9',
            fontSize: '13px',
            fontFamily: 'Inter, sans-serif',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {file.name}
          </p>
          <p style={{
            margin: '3px 0 0',
            color: '#64748b',
            fontSize: '11px',
            fontFamily: 'Inter, sans-serif',
            letterSpacing: '0.06em',
          }}>
            {fileTypeLabel} · {formatBytes(file.size)}
          </p>
        </div>

        <button
          onClick={() => onFileChange(null)}
          onMouseEnter={() => setHoverRemove(true)}
          onMouseLeave={() => setHoverRemove(false)}
          title="Remove file"
          style={{
            background: hoverRemove ? 'rgba(239,68,68,0.08)' : 'transparent',
            border: `1px solid ${hoverRemove ? 'rgba(239,68,68,0.25)' : '#1a2640'}`,
            borderRadius: '6px',
            padding: '6px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            color: hoverRemove ? '#f87171' : '#64748b',
            flexShrink: 0,
            transition: 'all 0.15s',
          }}
        >
          <X size={13} />
        </button>
      </div>
    )
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      style={{
        border: `2px dashed ${isDragging ? '#6366f1' : '#1a2640'}`,
        borderRadius: '10px',
        padding: '52px 32px',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '14px',
        background: isDragging
          ? 'rgba(99,102,241,0.04)'
          : 'rgba(10,15,30,0.4)',
        transition: 'border-color 0.2s, background 0.2s, box-shadow 0.2s',
        boxShadow: isDragging
          ? '0 0 0 1px rgba(99,102,241,0.15), inset 0 0 40px rgba(99,102,241,0.03)'
          : 'none',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Corner accents */}
      {[
        { top: 0, left: 0, borderTop: '1px solid #2d3f60', borderLeft: '1px solid #2d3f60' },
        { top: 0, right: 0, borderTop: '1px solid #2d3f60', borderRight: '1px solid #2d3f60' },
        { bottom: 0, left: 0, borderBottom: '1px solid #2d3f60', borderLeft: '1px solid #2d3f60' },
        { bottom: 0, right: 0, borderBottom: '1px solid #2d3f60', borderRight: '1px solid #2d3f60' },
      ].map((pos, i) => (
        <div key={i} style={{
          position: 'absolute',
          width: 14,
          height: 14,
          ...pos,
        }} />
      ))}

      <div style={{
        width: 46,
        height: 46,
        borderRadius: '10px',
        background: isDragging ? 'rgba(99,102,241,0.12)' : '#0a0f1e',
        border: `1px solid ${isDragging ? 'rgba(99,102,241,0.4)' : '#1a2640'}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.2s',
        boxShadow: isDragging ? '0 0 16px rgba(99,102,241,0.2)' : 'none',
      }}>
        <Upload size={20} color={isDragging ? '#818cf8' : '#64748b'} />
      </div>

      <div style={{ textAlign: 'center' }}>
        <p style={{
          margin: 0,
          color: isDragging ? '#ffffff' : '#cbd5e1',
          fontSize: '14px',
          fontFamily: 'Inter, sans-serif',
          fontWeight: 400,
          transition: 'color 0.2s',
        }}>
          Drop document here, or{' '}
          <span style={{ color: '#818cf8', fontWeight: 500 }}>browse</span>
        </p>
        <p style={{
          margin: '6px 0 0',
          color: '#475569',
          fontSize: '11px',
          fontFamily: 'Inter, sans-serif',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}>
          PDF · PNG · JPG · WEBP
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.webp"
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />
    </div>
  )
}
