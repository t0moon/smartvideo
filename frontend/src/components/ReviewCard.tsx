
import { useState } from 'react'
import { approveReview, rejectReview, addReviewComment, type ReviewTask } from '../api.ts'

export default function ReviewCard({ review, onResolved }: { review: ReviewTask; onResolved?: () => void }) {
  const [comment, setComment] = useState('')
  const [showComment, setShowComment] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleApprove = async () => {
    setSubmitting(true)
    try {
      await approveReview(review.review_id, comment)
      setComment('')
      onResolved?.()
    } catch (e) { alert(e) }
    finally { setSubmitting(false) }
  }

  const handleReject = async () => {
    if (!comment.trim()) {
      alert('Please provide a reason for rejection')
      return
    }
    setSubmitting(true)
    try {
      await rejectReview(review.review_id, comment)
      setComment('')
      onResolved?.()
    } catch (e) { alert(e) }
    finally { setSubmitting(false) }
  }

  const handleAddComment = async () => {
    if (!comment.trim()) return
    setSubmitting(true)
    try {
      await addReviewComment(review.review_id, comment)
      setComment('')
    } catch (e) { alert(e) }
    finally { setSubmitting(false) }
  }

  const isPending = review.status === 'pending'
  const stageLabels: Record<string, string> = {
    requirement: 'Requirement Review',
    storyboard: 'Storyboard Review',
    asset_prep: 'Asset Review',
    video_review: 'Video Review',
  }

  // content is free-form review payload; loosen typing for display access.
  const content = review.content as Record<string, any>

  return (
    <div style={{
      border: '2px solid #f59e0b', borderRadius: 8, padding: 20,
      background: '#fffbeb', marginBottom: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: '#92400e' }}>
          `{stageLabels[review.stage] || review.stage}`
        </h3>
        <span style={{
          background: isPending ? '#f59e0b' : '#22c55e',
          color: '#fff', padding: '2px 10px', borderRadius: 10, fontSize: 12,
        }}>{review.status}</span>
      </div>

      {/* Show content preview */}
      {content?.spec && (
        <div style={{ fontSize: 13, color: '#666', marginBottom: 12, background: '#fff', padding: 10, borderRadius: 6 }}>
          <strong>Video Spec:</strong> `{content.spec.duration_sec || '-'}s`, Style: `{content.spec.style || '-'}`
        </div>
      )}
      {content?.storyboard?.scenes && (
        <div style={{ fontSize: 13, color: '#666', marginBottom: 12, background: '#fff', padding: 10, borderRadius: 6 }}>
          <strong>Storyboard:</strong> `{content.storyboard.scenes.length}` scenes
        </div>
      )}

      {/* 需求一B: 人类可读故事板（用户可直接阅读/修改后继续） */}
      {review.stage === 'storyboard' && content?.readable_text && (
        <div style={{
          fontSize: 13, color: '#444', marginBottom: 12, background: '#fff',
          padding: 12, borderRadius: 6, border: '1px solid #fde68a',
          whiteSpace: 'pre-wrap', lineHeight: 1.6,
          maxHeight: 360, overflowY: 'auto',
        }}>
          <strong style={{ display: 'block', marginBottom: 6, color: '#92400e' }}>📋 故事板（可读版）：</strong>
          {content.readable_text}
        </div>
      )}

      {/* Comments */}
      {review.comments.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {review.comments.map((c, i) => (
            <div key={i} style={{ fontSize: 12, color: '#666', padding: '4px 0', borderBottom: '1px solid #fde68a' }}>
              <strong>{c.reviewer || 'Reviewer'}</strong>: {c.text} <span style={{ color: '#999' }}>({c.action})</span>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      {isPending && (
        <div>
          <textarea
            placeholder='Add a comment... (required for rejection)'
            value={comment}
            onChange={e => setComment(e.target.value)}
            rows={2}
            style={{
              width: '100%', padding: '8px 10px', border: '1px solid #fde68a',
              borderRadius: 6, fontSize: 13, resize: 'vertical', marginBottom: 8,
            }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleApprove} disabled={submitting}
              style={{ background: '#16a34a', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 6, fontSize: 13, fontWeight: 500 }}>
              Approve
            </button>
            <button onClick={handleReject} disabled={submitting}
              style={{ background: '#dc2626', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 6, fontSize: 13, fontWeight: 500 }}>
              Reject
            </button>
            <button onClick={() => setShowComment(!showComment)}
              style={{ background: '#eee', border: 'none', padding: '6px 16px', borderRadius: 6, fontSize: 13 }}>
              {showComment ? 'Cancel' : 'Comment'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
