-- MySQL 5.7+/8.x with case-sensitive keys and full emoji support.
CREATE TABLE IF NOT EXISTS audit_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            `entity_type` VARCHAR(191) NOT NULL,
            `entity_id` VARCHAR(191) NOT NULL,
            `action` VARCHAR(191) NOT NULL,
            `details` LONGTEXT,
            `created_at` VARCHAR(191) NOT NULL
        ,
 KEY `idx_audit_logs_action_created` (action, created_at)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS automations (
            `thread_id` VARCHAR(191) PRIMARY KEY,
            is_active INTEGER DEFAULT 0,
            `group_name` VARCHAR(255) DEFAULT '',
            `notify_username` VARCHAR(191) DEFAULT '',
            `control_method` VARCHAR(191) DEFAULT 'all_members',
            `updated_at` VARCHAR(191) DEFAULT ''
        ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS comment_history (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            `thread_id` VARCHAR(191),
            `username` VARCHAR(191),
            `post_code` VARCHAR(191),
            `comment_text` LONGTEXT,
            spam_score DOUBLE,
            is_format_valid INTEGER,
            `created_at` VARCHAR(191) NOT NULL,
            UNIQUE(thread_id, username, post_code)
        ,
 KEY `idx_comment_history_thread_user` (thread_id, username)
,
 KEY `idx_comment_history_user_created` (username, created_at)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS exemptions (
            `post_link` VARCHAR(512) NOT NULL,
            `username` VARCHAR(191) NOT NULL,
            PRIMARY KEY (post_link, username)
        ,
 KEY `idx_exemptions_username` (username)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS global_exemptions (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            `username` VARCHAR(191) NOT NULL UNIQUE,
            `created_at` VARCHAR(191) NOT NULL,
            `expires_at` VARCHAR(191) DEFAULT NULL,
            duration_days INTEGER DEFAULT 0
        ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS jobs (
            `id` VARCHAR(191) PRIMARY KEY, `kind` VARCHAR(191) NOT NULL, `payload` LONGTEXT NOT NULL,
            `state` VARCHAR(191) NOT NULL DEFAULT 'queued', created DOUBLE NOT NULL,
            updated DOUBLE NOT NULL, available DOUBLE NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            `owner` VARCHAR(191), lease_until DOUBLE, progress INTEGER NOT NULL DEFAULT 0,
            `message` VARCHAR(2048) NOT NULL DEFAULT '', `error` LONGTEXT, `result` LONGTEXT,
            `dedupe_key` VARCHAR(191) UNIQUE, `parent_id` VARCHAR(191), effects_started INTEGER NOT NULL DEFAULT 0
        ,
 KEY `jobs_pending` (state, available)
,
 KEY `jobs_created` (created)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS key_value (
            `key` VARCHAR(512) PRIMARY KEY,
            `value` LONGTEXT NOT NULL
        ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS login_attempts (
            `client` VARCHAR(191) PRIMARY KEY, failures INTEGER NOT NULL, expires DOUBLE NOT NULL
        ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS tokens (
            `username` VARCHAR(191) PRIMARY KEY,
            `full_name` VARCHAR(255) DEFAULT '',
            `password` VARCHAR(1024) DEFAULT '',
            `token` LONGTEXT,
            `android_id_yeni` VARCHAR(191) DEFAULT '',
            `user_agent` VARCHAR(2048) DEFAULT '',
            `device_id` VARCHAR(191) DEFAULT '',
            is_active INTEGER DEFAULT 1,
            `added_at` VARCHAR(191) DEFAULT '',
            `logout_reason` VARCHAR(1024) DEFAULT '',
            `logout_time` VARCHAR(191) DEFAULT '',
            `deleted_at` VARCHAR(191) DEFAULT '',
            relogin_attempts INTEGER DEFAULT 0,
            `last_relogin_failed_at` VARCHAR(191) DEFAULT ''
        ,
 KEY `idx_tokens_active_deleted` (is_active, deleted_at)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- Legacy data preservation only; the application does not read or write this table.
CREATE TABLE IF NOT EXISTS workers (
            `owner` VARCHAR(191) PRIMARY KEY, last_seen DOUBLE NOT NULL, `job_id` VARCHAR(191),
            stopped INTEGER NOT NULL DEFAULT 0
        ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
