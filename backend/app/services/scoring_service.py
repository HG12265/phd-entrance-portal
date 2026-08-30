from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer
from app.models.question import Question

kolkata_tz = ZoneInfo("Asia/Kolkata")

def calculate_attempt_score(db: Session, attempt: ExamAttempt) -> dict:
    """
    Evaluates candidate answers against the database correct options.
    Updates candidate answer rows and attempt fields *without* committing transactions.
    Returns evaluation summary dict.
    """
    server_now = datetime.now(kolkata_tz)
    
    # Load all CandidateAnswer rows
    candidate_answers = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id
    ).all()
    
    # Extract question IDs for queries
    q_ids = [ans.question_id for ans in candidate_answers]
    
    # Load corresponding questions
    questions = db.query(Question).filter(Question.id.in_(q_ids)).all()
    question_map = {q.id: q for q in questions}
    
    correct_count = 0
    wrong_count = 0
    unanswered_count = 0
    total_score = 0
    
    for ans in candidate_answers:
        q = question_map.get(ans.question_id)
        if not q:
            # Fallback if question was deleted from bank (should not happen normally)
            ans.is_correct = False
            ans.mark_awarded = 0
            unanswered_count += 1
            continue
            
        opt = ans.selected_option
        if not opt:
            ans.is_correct = False
            ans.mark_awarded = 0
            unanswered_count += 1
        elif opt.upper() == q.correct_option.upper():
            ans.is_correct = True
            ans.mark_awarded = q.marks if q.marks else 1
            correct_count += 1
            total_score += ans.mark_awarded
        else:
            ans.is_correct = False
            ans.mark_awarded = 0
            wrong_count += 1
            
    # Calculate pass/fail status
    result_status = "PASS" if total_score >= 28 else "FAIL"
    
    # Update attempt fields
    attempt.score = total_score
    attempt.correct_count = correct_count
    attempt.wrong_count = wrong_count
    attempt.unanswered_count = unanswered_count
    attempt.result_status = result_status
    attempt.evaluated_at = server_now
    
    return {
        "score": total_score,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "unanswered_count": unanswered_count,
        "result_status": result_status,
        "evaluated_at": server_now
    }
