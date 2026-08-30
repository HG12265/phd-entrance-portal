import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { getCurrentExam, startExam, saveAnswer, markQuestionStatus, getExamTimer, submitExam, logFullscreenEvent, getImageUrl } from '../../services/api';
import MathText from '../../components/MathText';
import { Lock, AlertCircle, ShieldCheck, ShieldAlert } from 'lucide-react';

export default function ExamPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Exam state
  const [attemptId, setAttemptId] = useState(null);
  const [attemptStatus, setAttemptStatus] = useState('in_progress');
  const [questions, setQuestions] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [candidate, setCandidate] = useState(null);
  
  // Timer state
  const [timeLeft, setTimeLeft] = useState(0);
  const [isTimeOver, setIsTimeOver] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Save feedback state
  const [saveState, setSaveState] = useState(''); // 'Saving...', 'Saved', 'Error'
  const saveTimeoutRef = useRef(null);

  // Full Screen Mode states
  const [isFullscreenActive, setIsFullscreenActive] = useState(false);
  const [isFullscreenBlocked, setIsFullscreenBlocked] = useState(false);
  const [isFullscreenSupported, setIsFullscreenSupported] = useState(true);

  const requestFullscreen = async () => {
    const docEl = document.documentElement;
    try {
      if (docEl.requestFullscreen) {
        await docEl.requestFullscreen();
        setIsFullscreenActive(true);
        setIsFullscreenBlocked(false);
      } else if (docEl.webkitRequestFullscreen) {
        await docEl.webkitRequestFullscreen();
        setIsFullscreenActive(true);
        setIsFullscreenBlocked(false);
      } else if (docEl.msRequestFullscreen) {
        await docEl.msRequestFullscreen();
        setIsFullscreenActive(true);
        setIsFullscreenBlocked(false);
      } else {
        setIsFullscreenSupported(false);
      }
    } catch (err) {
      console.warn('Fullscreen request blocked or failed:', err);
      setIsFullscreenBlocked(true);
    }
  };

  const exitFullscreenSafe = async () => {
    try {
      if ((document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement) && document.exitFullscreen) {
        await document.exitFullscreen();
      }
    } catch (err) {
      console.warn('Failed to exit fullscreen:', err);
    }
  };

  // Fullscreen exit detection
  useEffect(() => {
    const checkSupport = () => {
      const docEl = document.documentElement;
      return !!(docEl.requestFullscreen || docEl.webkitRequestFullscreen || docEl.msRequestFullscreen);
    };

    if (!checkSupport()) {
      setIsFullscreenSupported(false);
      if (attemptId) {
        logFullscreenEvent({ attempt_id: attemptId, event_type: 'fullscreen_unsupported', timestamp: new Date().toISOString() }).catch(() => {});
      }
      return;
    }

    const handleFullscreenChange = () => {
      const isCurrentlyFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement);
      setIsFullscreenActive(isCurrentlyFullscreen);
      
      if (!isCurrentlyFullscreen && !loading && attemptId) {
        logFullscreenEvent({ attempt_id: attemptId, event_type: 'exited_fullscreen', timestamp: new Date().toISOString() }).catch(() => {});
      } else if (isCurrentlyFullscreen && !loading && attemptId) {
        logFullscreenEvent({ attempt_id: attemptId, event_type: 'entered_fullscreen', timestamp: new Date().toISOString() }).catch(() => {});
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, [loading, attemptId]);

  // Initialize Exam attempt
  useEffect(() => {
    const initializeExam = async () => {
      try {
        // 1. Guard check from Phase 5
        await api.post('/api/candidate/exam/enter');
        
        // 2. Fetch candidate profile details
        const candidateUser = localStorage.getItem('candidate_user');
        if (candidateUser) {
          setCandidate(JSON.parse(candidateUser));
        } else {
          const profileRes = await api.get('/api/candidate/auth/me');
          setCandidate(profileRes.data);
        }

        // 3. Load or Start attempt
        let attemptData = null;
        try {
          const currentRes = await getCurrentExam();
          attemptData = currentRes.data;
        } catch (err) {
          if (err.response?.status === 404) {
            // No current attempt, start new one
            const startRes = await startExam();
            attemptData = startRes.data;
          } else {
            throw err;
          }
        }

        if (attemptData) {
          if (attemptData.redirect || attemptData.redirect_to_result || attemptData.exam_completed || attemptData.status === 'submitted' || attemptData.status === 'auto_submitted') {
            navigate('/candidate/result', { replace: true });
            return;
          }
          setAttemptId(attemptData.attempt_id);
          setAttemptStatus(attemptData.status);
          // Phase 17: Use questions exactly as returned by backend — selected_option already hydrated
          setQuestions(attemptData.questions);
          setTimeLeft(attemptData.remaining_seconds);
          
          if (attemptData.status === 'expired' || attemptData.remaining_seconds <= 0) {
            setIsTimeOver(true);
          }

          // Phase 17: Jump to first unanswered question (preserves answered state visibility)
          if (attemptData.questions && attemptData.questions.length > 0) {
            const firstUnansweredIdx = attemptData.questions.findIndex(
              q => !q.selected_option && q.answer_status !== 'answered' && q.answer_status !== 'answered_marked_for_review'
            );
            if (firstUnansweredIdx >= 0) {
              setCurrentIdx(firstUnansweredIdx);
            } else {
              // All answered — go to first question
              setCurrentIdx(0);
            }
          }
        }

        setLoading(false);
        // Automatically request fullscreen on check completion
        setTimeout(() => {
          requestFullscreen();
        }, 200);
      } catch (err) {
        console.error('Initialization error:', err);
        const detail = err.response?.data?.detail || err.response?.data;
        let errMsg = 'Failed to initialize exam session.';
        if (detail) {
          if (typeof detail === 'object') {
            if (detail.redirect_to_result || detail.exam_completed) {
              navigate('/candidate/result', { replace: true });
              return;
            }
            errMsg = detail.message || errMsg;
          } else {
            errMsg = detail;
          }
        }
        navigate('/candidate/instructions', { replace: true, state: { error: errMsg } });
      }
    };

    initializeExam();
  }, [navigate]);

  // Timer countdown hook
  useEffect(() => {
    if (loading || isTimeOver || timeLeft <= 0) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setIsTimeOver(true);
          setAttemptStatus('expired');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [loading, isTimeOver, timeLeft]);

  // Timer backend resync every 30 seconds
  useEffect(() => {
    if (loading || isTimeOver || !attemptId) return;

    const resyncInterval = setInterval(async () => {
      try {
        const timerRes = await getExamTimer(attemptId);
        const serverRemaining = timerRes.data.remaining_seconds;
        setTimeLeft(serverRemaining);
        if (timerRes.data.status === 'expired' || serverRemaining <= 0) {
          setIsTimeOver(true);
          setAttemptStatus('expired');
        }
      } catch (err) {
        console.error('Timer resync error:', err);
      }
    }, 30000);

    return () => clearInterval(resyncInterval);
  }, [loading, isTimeOver, attemptId]);

  // Auto-submit effect when time is over
  useEffect(() => {
    if (isTimeOver && attemptId && attemptStatus !== 'submitted' && attemptStatus !== 'auto_submitted') {
      const triggerAutoSubmit = async () => {
        if (isSubmitting) return;
        setIsSubmitting(true);
        try {
          await submitExam({
            attempt_id: attemptId,
            submission_type: 'auto'
          });
          navigate('/candidate/result', { replace: true });
        } catch (err) {
          console.error('Auto submission error, retrying once in 2 seconds...', err);
          setTimeout(async () => {
            try {
              await submitExam({
                attempt_id: attemptId,
                submission_type: 'auto'
              });
              navigate('/candidate/result', { replace: true });
            } catch (retryErr) {
              console.error('Auto submission retry failed:', retryErr);
              // Fallback redirect
              navigate('/candidate/result', { replace: true });
            }
          }, 2000);
        }
      };
      triggerAutoSubmit();
    }
  }, [isTimeOver, attemptId, navigate, attemptStatus]);

  // First view transition: 'not_visited' -> 'not_answered'
  useEffect(() => {
    if (loading || isTimeOver || questions.length === 0) return;

    const activeQ = questions[currentIdx];
    if (activeQ && activeQ.answer_status === 'not_visited') {
      const triggerFirstView = async () => {
        try {
          await markQuestionStatus({
            attempt_id: attemptId,
            question_id: activeQ.question_id,
            answer_status: 'not_answered'
          });
          
          // Update local state
          setQuestions((prev) =>
            prev.map((q, idx) =>
              idx === currentIdx ? { ...q, answer_status: 'not_answered' } : q
            )
          );
        } catch (err) {
          console.error('Failed to update question view status:', err);
        }
      };
      triggerFirstView();
    }
  }, [currentIdx, loading, isTimeOver, questions, attemptId]);

  // Save selected option
  const handleSelectOption = async (option) => {
    if (isTimeOver) return;
    if (isFullscreenSupported && !isFullscreenActive) return;

    const activeQ = questions[currentIdx];
    if (!activeQ) return;

    setSaveState('Saving...');
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    // Resolve target status locally for immediate UI update
    let nextStatus = 'answered';
    if (activeQ.answer_status === 'marked_for_review' || activeQ.answer_status === 'answered_marked_for_review') {
      nextStatus = 'answered_marked_for_review';
    }

    // Update local UI immediately
    setQuestions((prev) =>
      prev.map((q, idx) =>
        idx === currentIdx ? { ...q, selected_option: option, answer_status: nextStatus } : q
      )
    );

    try {
      await saveAnswer({
        attempt_id: attemptId,
        question_id: activeQ.question_id,
        selected_option: option
      });
      setSaveState('Saved');
      saveTimeoutRef.current = setTimeout(() => setSaveState(''), 3000);
    } catch (err) {
      console.error('Save answer error:', err);
      setSaveState('Error');
    }
  };

  // Clear Response handler
  const handleClearResponse = async () => {
    if (isTimeOver) return;
    if (isFullscreenSupported && !isFullscreenActive) return;

    const activeQ = questions[currentIdx];
    if (!activeQ) return;

    setSaveState('Saving...');
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    // Resolve target status locally for immediate UI update
    let nextStatus = 'not_answered';
    if (activeQ.answer_status === 'marked_for_review' || activeQ.answer_status === 'answered_marked_for_review') {
      nextStatus = 'marked_for_review';
    }

    // Update local UI immediately
    setQuestions((prev) =>
      prev.map((q, idx) =>
        idx === currentIdx ? { ...q, selected_option: null, answer_status: nextStatus } : q
      )
    );

    try {
      await saveAnswer({
        attempt_id: attemptId,
        question_id: activeQ.question_id,
        selected_option: null
      });
      setSaveState('Saved');
      saveTimeoutRef.current = setTimeout(() => setSaveState(''), 3000);
    } catch (err) {
      console.error('Clear response error:', err);
      setSaveState('Error');
    }
  };

  // Mark for Review toggle handler
  const handleToggleReview = async () => {
    if (isTimeOver) return;
    if (isFullscreenSupported && !isFullscreenActive) return;

    const activeQ = questions[currentIdx];
    if (!activeQ) return;

    setSaveState('Saving...');
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    const isCurrentlyMarked = activeQ.answer_status === 'marked_for_review' || activeQ.answer_status === 'answered_marked_for_review';
    const nextStatus = isCurrentlyMarked ? 'clear_review' : 'marked_for_review';

    try {
      const res = await markQuestionStatus({
        attempt_id: attemptId,
        question_id: activeQ.question_id,
        answer_status: nextStatus
      });

      // Update local state with status returned from backend
      setQuestions((prev) =>
        prev.map((q, idx) =>
          idx === currentIdx ? { ...q, answer_status: res.data.answer_status } : q
        )
      );

      setSaveState('Saved');
      saveTimeoutRef.current = setTimeout(() => setSaveState(''), 3000);
    } catch (err) {
      console.error('Toggle review status error:', err);
      setSaveState('Error');
    }
  };

  // Final Exam Submissions
  const handleFinalSubmit = async (type = 'manual') => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await exitFullscreenSafe();
      await submitExam({
        attempt_id: attemptId,
        submission_type: type
      });
      navigate('/candidate/result', { replace: true });
    } catch (err) {
      console.error('Submission error:', err);
      alert(err.response?.data?.detail || 'Failed to submit exam. Please try again.');
      setIsSubmitting(false);
    }
  };

  const [showReviewModal, setShowReviewModal] = useState(false);

  const handleManualSubmitClick = () => {
    setShowReviewModal(true);
  };

  // Navigations
  const handleNext = () => {
    if (currentIdx < questions.length - 1) {
      setCurrentIdx(currentIdx + 1);
    }
  };

  const handlePrev = () => {
    if (currentIdx > 0) {
      setCurrentIdx(currentIdx - 1);
    }
  };

  const handleSaveAndNext = () => {
    handleNext();
  };

  // Format seconds to HH:MM:SS
  const formatSeconds = (totalSecs) => {
    const hrs = Math.floor(totalSecs / 3600).toString().padStart(2, '0');
    const mins = Math.floor((totalSecs % 3600) / 60).toString().padStart(2, '0');
    const secs = (totalSecs % 60).toString().padStart(2, '0');
    return `${hrs}:${mins}:${secs}`;
  };

  // Summary counts
  const answeredCount = questions.filter(q => q.answer_status === 'answered' || q.answer_status === 'answered_marked_for_review').length;
  const markedReviewCount = questions.filter(q => q.answer_status === 'marked_for_review' || q.answer_status === 'answered_marked_for_review').length;
  const notAnsweredCount = questions.filter(q => q.answer_status === 'not_answered').length;
  const notVisitedCount = questions.filter(q => q.answer_status === 'not_visited').length;

  if (loading) {
    return (
      <div className="page-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="animate-pulse" style={{ fontSize: '1.2rem', fontWeight: 600 }}>Loading exam questions...</div>
        </div>
      </div>
    );
  }

  const activeQuestion = questions[currentIdx];

  const getSidebarBtnClass = (q, idx) => {
    let cls = 'palette-btn';
    if (idx === currentIdx) cls += ' current';
    
    const isMarked = q.answer_status === 'marked_for_review' || q.answer_status === 'answered_marked_for_review';
    if (isMarked) {
      cls += ' flagged';
    } else if (q.selected_option) {
      cls += ' answered';
    }
    return cls;
  };

  return (
    <div className="page-container" style={{ padding: '1rem', maxWidth: '1440px', margin: '0 auto' }}>
      
      {/* Time expired notification block */}
      {isTimeOver && (
        <div className="alert alert-danger" style={{ textAlign: 'center', fontSize: '1.1rem', padding: '1.5rem', marginBottom: '1.5rem', borderLeft: '5px solid var(--danger-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
          <Lock size={20} /> <strong>Time is over. Final submission will be handled in Phase 7.</strong>
        </div>
      )}

      {/* Top Details & Timer Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '1rem 1.5rem',
        backgroundColor: 'var(--card-background)',
        border: '1px solid var(--border-color)',
        borderRadius: '0.5rem',
        marginBottom: '1.5rem',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.05)',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div style={{ textAlign: 'left' }}>
          <h2 style={{ fontSize: '1.3rem', color: 'var(--primary-color)', margin: 0 }}>PhD Entrance Examination</h2>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            Candidate: <strong>{candidate?.name}</strong> ({candidate?.application_number}) | Department: <strong>{candidate?.applied_subject}</strong>
          </p>
        </div>
        
        {/* Visual Save Status Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {isFullscreenSupported ? (
            <span style={{
              fontSize: '0.85rem',
              fontWeight: 600,
              padding: '0.25rem 0.75rem',
              borderRadius: '1rem',
              backgroundColor: isFullscreenActive ? '#d1fae5' : '#fef2f2',
              color: isFullscreenActive ? '#065f46' : '#991b1b',
              border: `1px solid ${isFullscreenActive ? '#a7f3d0' : '#fecaca'}`,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem'
            }}>
              {isFullscreenActive ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
              {isFullscreenActive ? 'Full Screen: Active' : 'Full Screen: Not Active'}
            </span>
          ) : (
            <span style={{
              fontSize: '0.85rem',
              fontWeight: 600,
              padding: '0.25rem 0.75rem',
              borderRadius: '1rem',
              backgroundColor: '#f1f5f9',
              color: '#475569',
              border: '1px solid #cbd5e1',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem'
            }}>
              <AlertCircle size={14} /> Full Screen: Unsupported
            </span>
          )}

          {saveState && (
            <span style={{
              fontSize: '0.85rem',
              fontWeight: 600,
              padding: '0.25rem 0.75rem',
              borderRadius: '1rem',
              transition: 'all 0.3s ease',
              backgroundColor: saveState === 'Saving...' ? '#e0f2fe' : saveState === 'Saved' ? '#d1fae5' : '#fef2f2',
              color: saveState === 'Saving...' ? '#0369a1' : saveState === 'Saved' ? '#065f46' : '#991b1b'
            }}>
              {saveState === 'Saving...' ? '⏳ Saving answer...' : saveState === 'Saved' ? '✓ Auto-saved' : '⚠️ Save Failed'}
            </span>
          )}
          
          <div style={{
            padding: '0.5rem 1.25rem',
            backgroundColor: timeLeft < 300 ? '#fef2f2' : 'var(--background-color)',
            border: `1px solid ${timeLeft < 300 ? 'var(--danger-color)' : 'var(--border-color)'}`,
            borderRadius: '0.375rem',
            textAlign: 'right',
            minWidth: '150px'
          }}>
            <small style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Time Remaining
            </small>
            <strong style={{
              fontSize: '1.4rem',
              fontFamily: 'monospace',
              color: timeLeft < 300 ? 'var(--danger-color)' : 'var(--primary-color)',
              animation: timeLeft < 300 ? 'pulse 1s infinite alternate' : 'none'
            }}>
              {formatSeconds(timeLeft)}
            </strong>
          </div>
        </div>
      </div>

      {/* Main Exam Grid Layout */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 340px', gap: '1.5rem', alignItems: 'start' }}>
        
        {/* Left Side: Question Pane */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {activeQuestion ? (
            <div className="card" style={{ padding: '2rem', minHeight: '400px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', textAlign: 'left' }}>
              <div>
                
                {/* Question Metadata Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
                  <span className="user-badge" style={{ backgroundColor: 'var(--primary-light)', color: 'var(--primary-color)', fontSize: '0.85rem' }}>
                    Question {currentIdx + 1} of {questions.length}
                  </span>
                  {(activeQuestion.answer_status === 'marked_for_review' || activeQuestion.answer_status === 'answered_marked_for_review') && (
                    <span className="user-badge" style={{ backgroundColor: '#fef3c7', color: '#b45309', border: '1px solid #fde68a', fontSize: '0.85rem' }}>
                      ★ Flagged for Review
                    </span>
                  )}
                </div>

                {/* Question Text rendering with LaTeX & Tamil translations */}
                <div style={{ marginBottom: '2rem' }}>
                  <div style={{ fontSize: '1.15rem', color: 'var(--text-primary)', fontWeight: 500, lineHeight: 1.6, marginBottom: '1rem' }}>
                    <MathText text={activeQuestion.question_text} />
                  </div>

                  {activeQuestion.formula && (
                    <div style={{ margin: '1rem 0', padding: '1rem', backgroundColor: 'var(--background-color)', borderLeft: '4px solid var(--primary-color)', borderRadius: '0.25rem' }}>
                      <MathText text={activeQuestion.formula} />
                    </div>
                  )}

                  {activeQuestion.image_path && !activeQuestion.question_text?.includes(activeQuestion.image_path) && (
                    <div style={{ margin: '1rem 0', textAlign: 'center' }}>
                      <img 
                        src={getImageUrl(activeQuestion.image_path)} 
                        alt={`Question ${currentIdx + 1} Image`} 
                        style={{ 
                          maxWidth: '100%', 
                          maxHeight: '300px', 
                          objectFit: 'contain', 
                          borderRadius: '0.375rem', 
                          border: 'none',
                          padding: '0'
                        }} 
                        onError={(e) => {
                          e.target.src = activeQuestion.image_path;
                        }}
                      />
                    </div>
                  )}

                  {activeQuestion.question_tamil && (
                    <div className="tamil-text" style={{ fontSize: '1.05rem', color: 'var(--text-secondary)', borderTop: '1px dashed var(--border-color)', paddingTop: '1rem', marginTop: '1rem', lineHeight: 1.6 }}>
                      {activeQuestion.question_tamil}
                    </div>
                  )}
                </div>

                {/* Options Group List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginBottom: '2rem' }}>
                  {['option_a', 'option_b', 'option_c', 'option_d'].map((key, optIdx) => {
                    const optionChar = ['A', 'B', 'C', 'D'][optIdx];
                    const isSelected = activeQuestion.selected_option === optionChar;
                    return (
                      <label
                        key={key}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '1rem',
                          padding: '1rem 1.25rem',
                          border: isSelected ? '2px solid var(--primary-color)' : '1px solid var(--border-color)',
                          borderRadius: '0.5rem',
                          backgroundColor: isSelected ? 'var(--primary-light)' : 'var(--card-background)',
                          cursor: isTimeOver ? 'not-allowed' : 'pointer',
                          transition: 'all 0.15s ease',
                          opacity: isTimeOver ? 0.8 : 1
                        }}
                      >
                        <input
                          type="radio"
                          name="exam-options"
                          checked={isSelected}
                          disabled={isTimeOver}
                          onChange={() => handleSelectOption(optionChar)}
                          style={{ width: '20px', height: '20px', cursor: isTimeOver ? 'not-allowed' : 'pointer' }}
                        />
                        <span style={{ fontSize: '0.95rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <strong style={{ color: isSelected ? 'var(--primary-color)' : 'var(--text-secondary)' }}>{optionChar}.</strong>
                          <MathText text={activeQuestion[key]} />
                        </span>
                      </label>
                    );
                  })}
                </div>

              </div>

              {/* Bottom Navigational Action Bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem', marginTop: '1.5rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="btn btn-secondary" onClick={handlePrev} disabled={currentIdx === 0}>
                    ◀ Previous
                  </button>
                  <button className="btn btn-secondary" onClick={handleNext} disabled={currentIdx === questions.length - 1}>
                    Next ▶
                  </button>
                </div>
                
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-secondary"
                    style={{
                      borderColor: '#d97706',
                      color: '#d97706',
                      backgroundColor: activeQuestion.answer_status?.includes('marked_for_review') ? '#fef3c7' : 'transparent'
                    }}
                    onClick={handleToggleReview}
                    disabled={isTimeOver}
                  >
                    {activeQuestion.answer_status?.includes('marked_for_review') ? '★ Unmark Review' : '★ Mark for Review'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={handleClearResponse}
                    disabled={isTimeOver || !activeQuestion.selected_option}
                  >
                    Clear Response
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleSaveAndNext}
                    disabled={currentIdx === questions.length - 1}
                  >
                    Save & Next
                  </button>
                </div>
              </div>

            </div>
          ) : (
            <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
              <p>Failed to load question details.</p>
            </div>
          )}
        </div>

        {/* Right Side: Navigation Grid Palette, Stats, Legend & submit */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          {/* Question Grid Palette Panel */}
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 className="card-title" style={{ fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              Question Palette
            </h3>
            
            <div className="question-palette" style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, 1fr)',
              gap: '0.5rem',
              maxHeight: '340px',
              overflowY: 'auto',
              padding: '0.25rem'
            }}>
              {questions.map((q, idx) => (
                <button
                  key={q.question_id}
                  className={getSidebarBtnClass(q, idx)}
                  onClick={() => setCurrentIdx(idx)}
                  style={{
                    padding: '0.5rem 0',
                    fontWeight: 600,
                    borderRadius: '0.25rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxSizing: 'border-box'
                  }}
                >
                  {idx + 1}
                </button>
              ))}
            </div>

            {/* Metrics counts summary counts */}
            <div style={{
              marginTop: '1.5rem',
              borderTop: '1px solid var(--border-color)',
              paddingTop: '1rem',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '0.5rem',
              fontSize: '0.8rem',
              textAlign: 'left'
            }}>
              <div>Answered: <strong style={{ color: 'var(--success-color)' }}>{answeredCount}</strong></div>
              <div>Not Answered: <strong style={{ color: 'var(--danger-color)' }}>{notAnsweredCount}</strong></div>
              <div>Marked Review: <strong style={{ color: '#d97706' }}>{markedReviewCount}</strong></div>
              <div>Not Visited: <strong style={{ color: 'var(--text-secondary)' }}>{notVisitedCount}</strong></div>
            </div>
          </div>

          {/* Palette Legend Explainers */}
          <div className="card" style={{ padding: '1.25rem', fontSize: '0.85rem', textAlign: 'left' }}>
            <h4 style={{ margin: '0 0 0.75rem 0', textTransform: 'uppercase', fontSize: '0.8rem', letterSpacing: '0.03em', color: 'var(--text-secondary)' }}>
              Legend Indicator
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ width: '16px', height: '16px', borderRadius: '2px', backgroundColor: '#a7f3d0', border: '1px solid #047857' }} />
                <span>Answered</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ width: '16px', height: '16px', borderRadius: '2px', backgroundColor: '#fef3c7', border: '1px solid #fbbf24' }} />
                <span>Marked for Review</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ width: '16px', height: '16px', borderRadius: '2px', border: '1px solid #cbd5e1', backgroundColor: '#fff' }} />
                <span>Unanswered</span>
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <div className="card" style={{ padding: '1rem', borderLeft: '4px solid var(--danger-color)' }}>
            <button 
              className="btn btn-danger w-full animate-pulse" 
              onClick={handleManualSubmitClick}
              disabled={isSubmitting || isTimeOver}
            >
              {isSubmitting ? 'Submitting...' : 'Submit Examination'}
            </button>
            <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              Note: Once submitted, you cannot change answers.
            </p>
          </div>

        </div>

      </div>

      {/* Full screen blockage warning overlay */}
      {!loading && isFullscreenSupported && !isFullscreenActive && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          color: '#fff',
          zIndex: 99999,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          textAlign: 'center'
        }}>
          <h2 className="mb-4" style={{ color: '#fff' }}>Full Screen Mode Required</h2>
          <p className="mb-6" style={{ maxWidth: '500px', color: '#cbd5e1', lineHeight: '1.6' }}>
            To ensure examination integrity, the portal requires you to write the exam in full screen mode. 
            Answering questions is disabled until full screen mode is active.
          </p>
          <button className="btn btn-warning btn-lg animate-pulse" onClick={requestFullscreen}>
            Enter Full Screen
          </button>
        </div>
      )}

      {/* Final Submit Review Window/Modal */}
      {showReviewModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(8px)',
          color: 'var(--text-primary)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1.5rem',
        }}>
          <div className="card" style={{
            maxWidth: '800px',
            width: '100%',
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
            padding: '2rem',
            borderRadius: '0.75rem',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            backgroundColor: 'var(--card-background)',
            border: '1px solid var(--border-color)',
          }}>
            <h2 style={{ fontSize: '1.5rem', color: 'var(--primary-color)', marginBottom: '1rem', borderBottom: '2px solid var(--border-color)', paddingBottom: '0.75rem', flexShrink: 0 }}>
              Final Exam Review
            </h2>

            {/* Scrollable Middle Content */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              paddingRight: '0.5rem',
              marginBottom: '1rem'
            }}>
              {/* Candidate Details */}
              <div style={{
                backgroundColor: 'var(--background-color)',
                padding: '1rem',
                borderRadius: '0.375rem',
                marginBottom: '1.5rem',
                fontSize: '0.9rem',
                lineHeight: '1.5'
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '0.5rem' }}>
                  <strong>Applicant Name:</strong> <span>{candidate?.name}</span>
                  <strong>Application No:</strong> <span>{candidate?.application_number}</span>
                  <strong>Department:</strong> <span>{candidate?.department_name || candidate?.applied_subject}</span>
                  <strong>Subject:</strong> <span>{candidate?.subject || candidate?.applied_subject}</span>
                </div>
              </div>

              {/* Counts Summary */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '0.75rem',
                marginBottom: '1.5rem',
                textAlign: 'center'
              }}>
                <div style={{ padding: '0.75rem', backgroundColor: '#f1f5f9', borderRadius: '0.375rem' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{questions.length}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Total Questions</div>
                </div>
                <div style={{ padding: '0.75rem', backgroundColor: '#d1fae5', color: '#065f46', borderRadius: '0.375rem' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{answeredCount}</div>
                  <div style={{ fontSize: '0.75rem' }}>Answered</div>
                </div>
                <div style={{ padding: '0.75rem', backgroundColor: '#fde68a', color: '#b45309', borderRadius: '0.375rem' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{markedReviewCount}</div>
                  <div style={{ fontSize: '0.75rem' }}>Marked Review</div>
                </div>
                <div style={{ padding: '0.75rem', backgroundColor: '#fee2e2', color: '#991b1b', borderRadius: '0.375rem' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{questions.length - answeredCount}</div>
                  <div style={{ fontSize: '0.75rem' }}>Unanswered</div>
                </div>
              </div>

              {/* Color-Coded Question Legend & Navigation */}
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ fontSize: '0.9rem', marginBottom: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  Question Navigator Map (Click to Jump)
                </h4>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(10, 1fr)',
                  gap: '0.375rem',
                  maxHeight: '150px',
                  overflowY: 'auto',
                  padding: '0.5rem',
                  backgroundColor: 'var(--background-color)',
                  borderRadius: '0.375rem',
                  border: '1px solid var(--border-color)'
                }}>
                  {questions.map((q, idx) => {
                    const isMarked = q.answer_status === 'marked_for_review' || q.answer_status === 'answered_marked_for_review';
                    const isAnswered = q.selected_option !== null && q.selected_option !== undefined && q.selected_option !== '';
                    
                    let bgColor = '#ffffff';
                    let textColor = 'var(--text-secondary)';
                    let border = '1px solid var(--border-color)';
                    
                    if (isMarked) {
                      bgColor = '#fef3c7';
                      textColor = '#b45309';
                      border = '1px solid #fbbf24';
                    } else if (isAnswered) {
                      bgColor = '#d1fae5';
                      textColor = '#047857';
                      border = '1px solid #10b981';
                    }

                    return (
                      <button
                        key={q.question_id}
                        onClick={() => {
                          setCurrentIdx(idx);
                          setShowReviewModal(false);
                        }}
                        style={{
                          padding: '0.375rem 0',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          backgroundColor: bgColor,
                          color: textColor,
                          border: border,
                          borderRadius: '0.25rem',
                          cursor: 'pointer',
                          textAlign: 'center',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {idx + 1}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Scrollable Questions list for review */}
              <div style={{
                border: '1px solid var(--border-color)',
                borderRadius: '0.375rem',
                backgroundColor: 'var(--background-color)',
                overflow: 'hidden'
              }}>
                <div style={{
                  padding: '0.75rem 1rem',
                  backgroundColor: 'var(--card-background)',
                  borderBottom: '1px solid var(--border-color)',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  fontSize: '0.95rem',
                  textAlign: 'left'
                }}>
                  Review Your Answers (1 to {questions.length})
                </div>
                <div style={{
                  padding: '1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.25rem'
                }}>
                  {questions.map((q, idx) => {
                    return (
                      <div key={q.question_id} style={{
                        paddingBottom: '1.25rem',
                        borderBottom: idx === questions.length - 1 ? 'none' : '1px solid var(--border-color)',
                        textAlign: 'left'
                      }}>
                        <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.75rem', color: 'var(--text-primary)', display: 'flex', gap: '0.5rem' }}>
                          <span>{idx + 1}.</span>
                          <div style={{ flex: 1 }}>
                            <MathText text={q.question_text} />
                          </div>
                        </div>
                        
                        {q.image_path && (
                          <div style={{ margin: '0.5rem 0 0.5rem 1.5rem', textAlign: 'left' }}>
                            <img 
                              src={getImageUrl(q.image_path)} 
                              alt={`Question ${idx + 1} Image`} 
                              style={{ 
                                maxWidth: '100%', 
                                maxHeight: '180px', 
                                objectFit: 'contain', 
                                borderRadius: '0.25rem', 
                                border: 'none',
                                padding: '0'
                              }} 
                              onError={(e) => {
                                e.target.src = q.image_path;
                              }}
                            />
                          </div>
                        )}
                        
                        {/* Render the 4 option boxes */}
                        <div style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                          gap: '0.75rem',
                          marginTop: '0.5rem'
                        }}>
                          {['A', 'B', 'C', 'D'].map(opt => {
                            const optionKey = `option_${opt.toLowerCase()}`;
                            const optionText = q[optionKey];
                            const isSelected = q.selected_option === opt;
                            
                            // Style selected answer with grey color (not green)
                            const optionBgColor = isSelected ? '#e2e8f0' : 'var(--card-background)';
                            const optionBorderColor = isSelected ? '#64748b' : 'var(--border-color)';
                            const optionTextColor = isSelected ? '#1e293b' : 'var(--text-primary)';
                            const optionFontWeight = isSelected ? '600' : 'normal';
                            
                            return (
                              <div
                                key={opt}
                                style={{
                                  padding: '0.625rem 0.875rem',
                                  borderRadius: '0.375rem',
                                  border: `1px solid ${optionBorderColor}`,
                                  backgroundColor: optionBgColor,
                                  color: optionTextColor,
                                  fontWeight: optionFontWeight,
                                  fontSize: '0.85rem',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '0.5rem',
                                  transition: 'all 0.15s ease'
                                }}
                              >
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  width: '20px',
                                  height: '20px',
                                  borderRadius: '50%',
                                  backgroundColor: isSelected ? '#64748b' : '#f1f5f9',
                                  color: isSelected ? '#ffffff' : '#475569',
                                  fontSize: '0.75rem',
                                  fontWeight: 700
                                }}>
                                  {opt}
                                </span>
                                <div style={{ flex: 1 }}>
                                  <MathText text={optionText} />
                                </div>
                                {isSelected && (
                                  <span style={{
                                    fontSize: '0.65rem',
                                    color: '#475569',
                                    backgroundColor: '#cbd5e1',
                                    padding: '0.125rem 0.375rem',
                                    borderRadius: '0.25rem',
                                    fontWeight: 600,
                                    whiteSpace: 'nowrap'
                                  }}>
                                    Selected
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Footer Buttons: Fixed at bottom */}
            <div style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '1rem',
              marginTop: 'auto',
              borderTop: '1px solid var(--border-color)',
              paddingTop: '1rem',
              flexShrink: 0
            }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowReviewModal(false)}
                style={{ minWidth: '130px' }}
              >
                Return to Exam
              </button>
              <button
                className="btn btn-danger"
                onClick={() => handleFinalSubmit('manual')}
                disabled={isSubmitting}
                style={{ minWidth: '150px' }}
              >
                {isSubmitting ? 'Submitting...' : 'Confirm & Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
