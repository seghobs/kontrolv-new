import hashlib
import time
from pathlib import Path
from flask import Flask, jsonify, request, redirect, session, g
from flask_wtf.csrf import CSRFProtect, CSRFError
from app_core.config import get_config
from app_core.routes.admin import admin_bp
from app_core.routes.main import main_bp
from app_core.storage import init_storage

def create_app():
    config = get_config()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config)

    # CSRF Koruması Tamamen Devre Dışı
    app.config["WTF_CSRF_ENABLED"] = False
    csrf = CSRFProtect()
    csrf.init_app(app)

    # Content versions keep edited assets fresh without downloading unchanged files.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600
    static_root = Path(app.static_folder)
    asset_versions = {
        path.relative_to(static_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        for path in static_root.rglob("*") if path.is_file()
    }

    @app.url_defaults
    def version_static_assets(endpoint, values):
        if endpoint == "static" and "v" not in values:
            version = asset_versions.get(values.get("filename"))
            if version:
                values["v"] = version

    init_storage()

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    from app_core.routes.history import history_bp
    app.register_blueprint(history_bp)

    @app.before_request
    def make_session_permanent():
        g.request_started = time.perf_counter()
        if request.endpoint != "static":
            session.permanent = True


    # Keep account data private while allowing static asset caching.
    @app.after_request
    def add_no_cache_headers(response):
        started = getattr(g, "request_started", None)
        if started is not None:
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
            if request.path.startswith(("/result/", "/api/task_status/")):
                app.logger.info("Request %s status=%s duration_ms=%.1f",
                                request.path, response.status_code, elapsed_ms)
        if request.endpoint == "static":
            return response
        # Private HTML and API responses must never be cached.
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, "
            "proxy-revalidate, max-age=0, s-maxage=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Surrogate-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"success": False, "message": "Sayfa bulunamadi"}), 404

    @app.errorhandler(500)
    def server_error(_error):
        return jsonify({"success": False, "message": "Sunucu hatasi"}), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"CSRF validation failed: {e.description} for path {request.path}")
        
        # Check if request is AJAX
        is_ajax = (
            request.is_json or 
            request.headers.get("X-Requested-With") == "XMLHttpRequest" or 
            request.path.startswith("/api/") or
            "application/json" in request.headers.get("Accept", "")
        )
        
        if is_ajax:
            return jsonify({
                "success": False,
                "message": "Güvenlik doğrulama anahtarı (CSRF) zaman aşımına uğradı veya oturumunuz sonlandı. Lütfen sayfayı yenileyip tekrar deneyin."
            }), 400
            
        # HTML form submissions: redirect back to referrer page
        target = request.referrer or "/"
        if "csrf_expired=1" not in target:
            if "?" in target:
                target += "&csrf_expired=1"
            else:
                target += "?csrf_expired=1"
                
        return redirect(target)

    return app
