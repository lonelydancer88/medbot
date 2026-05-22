import type { Diagnosis } from '../types'

interface Props {
  diagnoses: Diagnosis[]
  onNewSession: () => void
}

export function DiagnosisCard({ diagnoses, onNewSession }: Props) {
  if (!diagnoses.length) return null

  return (
    <div
      style={{
        background: '#fefce8',
        border: '1px solid #eab308',
        borderRadius: '12px',
        padding: '20px',
        marginTop: '24px',
      }}
    >
      <h3 style={{ margin: '0 0 12px', color: '#854d0e' }}>📋 诊断结果</h3>
      {diagnoses.map((d, i) => (
        <div
          key={i}
          style={{
            padding: '10px 12px',
            marginBottom: '8px',
            background: '#fff',
            borderRadius: '8px',
          }}
        >
          <strong>{d.disease}</strong>
          <span
            style={{
              display: 'inline-block',
              marginLeft: '8px',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              background:
                d.probability === '高'
                  ? '#fee2e2'
                  : d.probability === '中'
                  ? '#fef3c7'
                  : '#dbeafe',
              color:
                d.probability === '高'
                  ? '#991b1b'
                  : d.probability === '中'
                  ? '#92400e'
                  : '#1e40af',
            }}
          >
            {d.probability}可能性
          </span>
          <p style={{ margin: '4px 0 0', fontSize: '14px', color: '#4b5563' }}>
            {d.reason}
          </p>
        </div>
      ))}
      <button
        onClick={onNewSession}
        style={{
          marginTop: '12px',
          padding: '10px 20px',
          background: '#2563eb',
          color: '#fff',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer',
          fontSize: '14px',
        }}
      >
        开始新的问诊
      </button>
    </div>
  )
}
