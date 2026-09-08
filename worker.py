"""Run separately: python worker.py (never import this from WSGI)."""
import argparse
import datetime
import logging
import multiprocessing
import signal
import time
import uuid

import pytz
from app_core import jobs

logger = logging.getLogger(__name__)


def execute(job):
    job_id, owner = job['id'], job['owner']
    try:
        if job['kind'] == 'manual':
            from app_core.routes.main import run_manual_control
            payload = dict(job['payload'])
            parent = jobs.get_job(job['parent_id']) if job['parent_id'] else None
            payload['prev_result'] = parent['result'] if parent else None
            payload['progress_callback'] = lambda current,total,msg: jobs.progress(job_id,owner,current,total,msg)
            result = run_manual_control(**payload)
        elif job['kind'] == 'preset':
            from app_core.features import run_preset
            result = run_preset(job['payload'], lambda current,total,msg: jobs.progress(job_id,owner,current,total,msg))
        elif job['kind'] == 'automation':
            from app_core.automation import run_automation_for_thread
            result = run_automation_for_thread(**job['payload'],
                before_send=lambda: jobs.mark_effects_started(job_id,owner),
                on_result=lambda result: jobs.snapshot(job_id,owner,result))
        else:
            raise ValueError('Bilinmeyen iş türü')
        if not jobs.complete(job_id, owner, result or {}):
            logger.warning('Job ownership expired: %s', job_id)
    except Exception as error:
        logger.exception('Job failed: %s', job_id)
        jobs.fail(job_id, owner, error)


def schedule_due(now=None):
    from app_core.storage import get_global_automation_status, get_global_automation_settings, _connect
    from app_core.automation import load_automations
    if not get_global_automation_status():
        return
    now = now or datetime.datetime.now(pytz.timezone('Europe/Istanbul'))
    settings = get_global_automation_settings()
    for slot in settings.get('times', '').split(','):
        slot = slot.strip()
        try:
            hour, minute = map(int, slot.split(':'))
            scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            continue
        if scheduled > now:
            continue
        date = now.strftime('%Y-%m-%d')
        for thread_id, config in load_automations().items():
            if not config.get('is_active'):
                continue
            # Respect pre-upgrade locks to avoid repeating old notifications.
            conn = _connect()
            try:
                old = conn.execute('SELECT 1 FROM key_value WHERE key=?',
                                   (f'auto_lock_{thread_id}_{date}_{slot}',)).fetchone()
            finally:
                conn.close()
            if old:
                continue
            jobs.enqueue('automation', {'thread_id': str(thread_id), 'target_date': date},
                         dedupe_key=f'auto:{thread_id}:{date}:{slot}')


def run(once=False, timeout=1800):
    from app_core.storage import init_storage
    init_storage()
    jobs.import_legacy()
    context = multiprocessing.get_context('spawn')
    owner = uuid.uuid4().hex
    active = None
    last_schedule = 0
    try:
        while True:
            jobs.worker_presence(owner, active[0]["id"] if active else None)
            now = time.monotonic()
            if now - last_schedule >= 30:
                schedule_due()
                last_schedule = now
            if active:
                job, process, started = active
                if not process.is_alive():
                    process.join()
                    jobs.finish_cancel(job['id'], owner)
                    jobs.fail(job['id'], owner, 'İşçi beklenmedik şekilde kapandı.')
                    active = None
                    if once:
                        return
                elif now - started > timeout:
                    process.terminate()
                    process.join(5)
                    if process.is_alive():
                        process.kill()
                        process.join()
                    jobs.finish_cancel(job['id'], owner)
                    jobs.fail(job['id'], owner, 'Denetim süre sınırını aştı.')
                    active = None
                    if once:
                        return
                elif not jobs.heartbeat(job['id'], owner):
                    process.terminate()
                    process.join(5)
                    if process.is_alive():
                        process.kill()
                        process.join()
                    jobs.finish_cancel(job['id'], owner)
                    active = None
            jobs.recover_stale()
            if active is None:
                job = jobs.claim(owner)
                if job:
                    process = context.Process(target=execute, args=(job,), daemon=True)
                    process.start()
                    active = job, process, time.monotonic()
                elif once:
                    return
            time.sleep(2)
    finally:
        if active:
            job, process, _ = active
            if process.is_alive():
                process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
            jobs.finish_cancel(job['id'], owner)
            jobs.fail(job['id'], owner, 'İşçi kapatıldı; iş kurtarma için kaydedildi.')
        jobs.worker_presence(owner, stopped=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Process at most one job')
    parser.add_argument('--timeout', type=int, default=1800, help='Maximum seconds per job')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    def stop_worker(*_args):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, stop_worker)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, stop_worker)
    try:
        run(args.once, max(30,args.timeout))
    except KeyboardInterrupt:
        pass
