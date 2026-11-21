"""Compatibility entry point for the account-isolated Luma CAA login engine."""
class LoginError(Exception):
    def __init__(self,message,error_type="UNKNOWN",status_code=None,details=None):
        super().__init__(message);self.message=message;self.error_type=error_type
        self.status_code=status_code;self.details=details or {}
    def to_dict(self):
        return dict(message=self.message,error_type=self.error_type,status_code=self.status_code,details=self.details)


def giris_yap(username,password,android_id="",user_agent="",device_id=""):
    from flask import has_request_context
    from app_core import luma_login
    from app_core.routes.login import owner
    try:
        result=luma_login.start(username,password,owner=owner() if has_request_context() else "internal",fresh=True)
    except Exception as error:
        raise LoginError("Giriş başlatılamadı. Luma giriş ekranından devam edin.","LOGIN_FAILED",400) from error
    if result['stage']!='done':
        raise LoginError(result['message'],"VERIFICATION_REQUIRED",400,{'flow_id':result['id']})
    from app_core.storage import load_tokens
    record=next(t for t in load_tokens() if t['username']==result['username'])
    return record['token'],record['android_id_yeni'],record['user_agent'],record['device_id']
