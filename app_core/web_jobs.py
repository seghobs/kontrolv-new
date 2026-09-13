"""Run requested checks within an HTTP request; no background service required."""
import time
import uuid
from app_core import jobs


def execute_job(job_id, allow_automation=False):
    existing = jobs.get_job_state(job_id)
    if not existing:
        return {'error':'Denetim bulunamadı.'}, 404
    if existing['kind'] not in ('manual','preset','automation','member'):
        return {'error':'Bu denetim türü desteklenmiyor.'}, 400
    if existing['kind'] == 'automation' and not allow_automation:
        return {'error':'Bu işlem için admin girişi gerekli.'}, 403
    job = jobs.claim_request(job_id, 'request-' + uuid.uuid4().hex)
    if not job:
        return jobs.public_status(jobs.get_job_state(job_id)), 200
    execute_claimed(job)
    return jobs.public_status(jobs.get_job_state(job_id)), 200


def execute_claimed(job):
    job_id, owner = job['id'], job['owner']
    started = time.monotonic()
    def check_active():
        current = jobs.get_job_state(job_id)
        if not current or current['state'] != 'running' or current['owner'] != owner:
            raise RuntimeError('Denetim durduruldu.')
        if time.monotonic() - started > 150:
            raise RuntimeError('İstek süresi aşıldı; daha az gönderi seçerek yeniden deneyin.')
    def progress(current, total, message):
        check_active()
        jobs.progress(job_id, owner, current, total, message)
    try:
        payload = dict(job['payload'])
        if job['kind'] == 'manual':
            from app_core.routes.main import run_manual_control
            parent = jobs.get_job(job['parent_id']) if job['parent_id'] else None
            payload['prev_result'] = parent['result'] if parent else None
            payload['progress_callback'] = progress
            result = run_manual_control(**payload)
        elif job['kind'] == 'member':
            from app_core.member_analysis import run
            result = run(payload, progress)
        elif job['kind'] == 'preset':
            from app_core.features import run_preset
            result = run_preset(payload, progress)
        else:
            from app_core.automation import run_automation_for_thread
            def before_send():
                check_active()
                jobs.mark_effects_started(job_id, owner)
            result = run_automation_for_thread(**payload, before_send=before_send,
                on_result=lambda result: jobs.snapshot(job_id,owner,result))
        check_active()
        jobs.complete(job_id, owner, result or {})
    except Exception as error:
        jobs.fail(job_id, owner, error)
    finally:
        jobs.finish_cancel(job_id, owner)
