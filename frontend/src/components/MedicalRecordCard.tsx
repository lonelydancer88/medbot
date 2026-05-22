interface Props {
  content: string
}

export function MedicalRecordCard({ content }: Props) {
  if (!content) return null

  return (
    <div
      style={{
        background: '#f0fdf4',
        border: '1px solid #22c55e',
        borderRadius: '12px',
        padding: '20px',
        marginTop: '24px',
      }}
    >
      <h3 style={{ margin: '0 0 12px', color: '#166534', fontSize: '16px' }}>
        病历总结
      </h3>
      <div
        style={{
          fontSize: '14px',
          lineHeight: 1.8,
          color: '#1a202c',
          whiteSpace: 'pre-wrap',
        }}
      >
        {content}
      </div>
    </div>
  )
}
