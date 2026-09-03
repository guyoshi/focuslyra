from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .concept_service import ConceptServiceError, enrich_concept, list_concepts, save_concept
from .diagnostic_service import (
    DiagnosticServiceError,
    finalise,
    get_attempt,
    latest_completed,
    save_part,
    start_english_diagnostic,
)
from .learning_engine import LearningEngineError, analyse_submission
from .memory_index import index_source, index_status, retrieve
from .plan_calendar_service import (
    PlanCalendarError,
    auto_schedule_if_enabled,
    load_settings as load_plan_calendar_settings,
    save_settings as save_plan_calendar_settings,
    schedule_adaptive_plan,
)
from .progress_service import learner_progress
from .review_service import ReviewServiceError, due_reviews, grade_review
from .session_planner import build_daily_plan

router = APIRouter(tags=['learning-v2'])


class ReviewGradePayload(BaseModel):
    rating: str


class ConceptPayload(BaseModel):
    concept_key: str | None = None
    label: str
    visual: str | None = None
    visual_kind: str | None = None
    senses: list[Any] = Field(default_factory=list)
    expressions: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class DiagnosticPartPayload(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


class DiagnosticTextPayload(BaseModel):
    text: str
    prompt: str | None = None


class CalendarPlanSettingsPayload(BaseModel):
    auto_schedule: bool | None = None
    window_start: str | None = None
    window_end: str | None = None
    mode: str | None = None
    days_ahead: int | None = None


class CalendarPlanPayload(BaseModel):
    target_date: str
    mode: str = 'normal'
    window_start: str | None = None
    window_end: str | None = None


@router.get('/study/plan')
def study_plan(mode: str = 'normal'):
    return build_daily_plan('minimum' if mode == 'minimum' else 'normal')


@router.get('/review/due')
def review_due(limit: int = 20, language_code: str | None = None):
    return due_reviews(limit=limit, language_code=language_code)


@router.post('/review/{item_id}/grade')
def review_grade(item_id: int, payload: ReviewGradePayload):
    try:
        return {'ok': True, 'item': grade_review(item_id, payload.rating)}
    except ReviewServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/concepts')
def concepts_list(limit: int = 200):
    return list_concepts(limit)


@router.post('/concepts')
def concepts_save(payload: ConceptPayload):
    try:
        return {'ok': True, 'concept': save_concept(payload.model_dump())}
    except ConceptServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/concepts/{concept_id}/enrich')
def concepts_enrich(concept_id: int):
    try:
        return {'ok': True, 'concept': enrich_concept(concept_id)}
    except ConceptServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/memory/index-status')
def memory_index_status():
    return index_status()


@router.post('/memory/sources/{source_id}/index')
def memory_index_source(source_id: str, sync_first: bool = True):
    try:
        return {'ok': True, **index_source(source_id, sync_first=sync_first)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/memory/search')
def memory_search(q: str, limit: int = 4):
    return {'query': q, 'results': retrieve(q, limit=limit)}


@router.get('/progress')
def progress():
    return learner_progress()


@router.post('/diagnostic/english/start')
def diagnostic_start():
    return start_english_diagnostic()


@router.get('/diagnostic/latest')
def diagnostic_latest():
    return {'attempt': latest_completed()}


@router.get('/diagnostic/{attempt_id}')
def diagnostic_get(attempt_id: int):
    try:
        return get_attempt(attempt_id)
    except DiagnosticServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/diagnostic/{attempt_id}/part/{part_id}')
def diagnostic_part(attempt_id: int, part_id: str, payload: DiagnosticPartPayload):
    try:
        return save_part(attempt_id, part_id, payload.result)
    except DiagnosticServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/diagnostic/{attempt_id}/text/{part_id}')
def diagnostic_text(attempt_id: int, part_id: str, payload: DiagnosticTextPayload):
    try:
        result = analyse_submission(
            language_code='en-GB',
            modality=f'diagnostic-{part_id}',
            learner_text=payload.text,
            exercise_prompt=payload.prompt or part_id,
            metadata={'diagnostic_attempt_id': attempt_id, 'diagnostic_part': part_id},
        )
        return save_part(attempt_id, part_id, result)
    except (DiagnosticServiceError, LearningEngineError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/diagnostic/{attempt_id}/finalise')
def diagnostic_finalise(attempt_id: int):
    try:
        return finalise(attempt_id)
    except DiagnosticServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/calendar/plan-settings')
def calendar_plan_settings():
    return load_plan_calendar_settings()


@router.put('/calendar/plan-settings')
def calendar_plan_settings_save(payload: CalendarPlanSettingsPayload):
    return save_plan_calendar_settings({key: value for key, value in payload.model_dump().items() if value is not None})


@router.post('/calendar/schedule-plan')
def calendar_schedule_plan(payload: CalendarPlanPayload):
    try:
        return schedule_adaptive_plan(
            payload.target_date,
            mode=payload.mode,
            window_start=payload.window_start,
            window_end=payload.window_end,
        )
    except PlanCalendarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/calendar/auto-plan')
def calendar_auto_plan():
    try:
        return auto_schedule_if_enabled()
    except PlanCalendarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
