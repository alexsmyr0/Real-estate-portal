SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- ------------------------------------------------------------
-- USERS AND AUTHENTICATION
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email             VARCHAR(255) NOT NULL,
    password_hash     VARCHAR(255) NOT NULL,
    full_name         VARCHAR(150) NULL,
    phone             VARCHAR(30) NULL,
    role              ENUM('USER', 'SUPERVISOR', 'ADMIN') NOT NULL DEFAULT 'USER',
    is_active         TINYINT(1) NOT NULL DEFAULT 1,
    email_verified_at DATETIME NULL,
    deleted_at        DATETIME NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_email (email),
    KEY idx_users_role (role),
    KEY idx_users_deleted_at (deleted_at),
    CONSTRAINT chk_users_email_format CHECK (email LIKE '%_@_%._%')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Stores hashed 2FA login tokens sent via email.
CREATE TABLE IF NOT EXISTS login_2fa_tokens (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id       BIGINT UNSIGNED NOT NULL,
    token_hash    CHAR(64) NOT NULL,
    sent_to_email VARCHAR(255) NOT NULL,
    sent_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    DATETIME NOT NULL,
    verified_at   DATETIME NULL,
    is_revoked    TINYINT(1) NOT NULL DEFAULT 0,
    attempts_used SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    max_attempts  SMALLINT UNSIGNED NOT NULL DEFAULT 5,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_2fa_user_status (user_id, is_revoked, verified_at, expires_at),
    KEY idx_2fa_expires_at (expires_at),
    CONSTRAINT fk_2fa_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_2fa_expiry CHECK (expires_at > sent_at),
    CONSTRAINT chk_2fa_attempts CHECK (attempts_used <= max_attempts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Exactly one active session per user (PRIMARY KEY on user_id enforces it).
CREATE TABLE IF NOT EXISTS active_sessions (
    user_id            BIGINT UNSIGNED NOT NULL,
    session_token_hash CHAR(64) NOT NULL,
    ip_address         VARCHAR(45) NULL,
    user_agent         VARCHAR(255) NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at         DATETIME NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE KEY uk_active_sessions_token_hash (session_token_hash),
    KEY idx_active_sessions_expires_at (expires_at),
    CONSTRAINT fk_active_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_active_session_expiry CHECK (expires_at > created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- PROPERTY LISTINGS AND SEARCH FILTER DATA
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS properties (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title              VARCHAR(200) NOT NULL,
    description        TEXT NULL,
    category           ENUM('RESIDENTIAL', 'COMMERCIAL', 'RENTAL') NOT NULL,
    status             ENUM('AVAILABLE', 'UNAVAILABLE', 'PENDING', 'REMOVED') NOT NULL DEFAULT 'AVAILABLE',
    country            VARCHAR(100) NULL,
    city               VARCHAR(100) NOT NULL,
    area               VARCHAR(120) NULL,
    address_line       VARCHAR(255) NULL,
    postal_code        VARCHAR(20) NULL,
    price              DECIMAL(12, 2) NOT NULL,
    currency           CHAR(3) NOT NULL DEFAULT 'USD',
    bedrooms           SMALLINT UNSIGNED NULL,
    bathrooms          DECIMAL(3, 1) NULL,
    area_sq_m          DECIMAL(10, 2) NULL,
    listed_by_admin_id BIGINT UNSIGNED NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    removed_at         DATETIME NULL,
    PRIMARY KEY (id),
    KEY idx_properties_category_status (category, status),
    KEY idx_properties_city_area (city, area),
    KEY idx_properties_price (price),
    KEY idx_properties_bedrooms (bedrooms),
    KEY idx_properties_listed_by_admin (listed_by_admin_id),
    CONSTRAINT fk_properties_admin FOREIGN KEY (listed_by_admin_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_properties_price CHECK (price >= 0),
    CONSTRAINT chk_properties_bedrooms CHECK (bedrooms IS NULL OR bedrooms <= 50),
    CONSTRAINT chk_properties_bathrooms CHECK (bathrooms IS NULL OR bathrooms <= 50),
    CONSTRAINT chk_properties_area CHECK (area_sq_m IS NULL OR area_sq_m >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS amenities (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name       VARCHAR(80) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_amenities_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS property_amenities (
    property_id BIGINT UNSIGNED NOT NULL,
    amenity_id  BIGINT UNSIGNED NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (property_id, amenity_id),
    KEY idx_property_amenities_amenity (amenity_id),
    CONSTRAINT fk_property_amenities_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CONSTRAINT fk_property_amenities_amenity FOREIGN KEY (amenity_id) REFERENCES amenities(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS property_images (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    property_id   BIGINT UNSIGNED NOT NULL,
    image_url     VARCHAR(500) NOT NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_property_images_order (property_id, display_order),
    KEY idx_property_images_property (property_id),
    CONSTRAINT fk_property_images_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- USER INTERACTIONS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS user_favorites (
    user_id     BIGINT UNSIGNED NOT NULL,
    property_id BIGINT UNSIGNED NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, property_id),
    KEY idx_user_favorites_property (property_id),
    CONSTRAINT fk_user_favorites_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_favorites_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS viewing_requests (
    id                         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id                    BIGINT UNSIGNED NOT NULL,
    property_id                BIGINT UNSIGNED NOT NULL,
    requested_datetime         DATETIME NOT NULL,
    status                     ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED') NOT NULL DEFAULT 'PENDING',
    note                       VARCHAR(500) NULL,
    confirmation_email_sent_at DATETIME NULL,
    processed_by_admin_id      BIGINT UNSIGNED NULL,
    created_at                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_viewing_requests_user (user_id),
    KEY idx_viewing_requests_property (property_id),
    KEY idx_viewing_requests_status_datetime (status, requested_datetime),
    KEY idx_viewing_requests_admin (processed_by_admin_id),
    CONSTRAINT fk_viewing_requests_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_viewing_requests_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CONSTRAINT fk_viewing_requests_admin FOREIGN KEY (processed_by_admin_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS property_inquiries (
    id                         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id                    BIGINT UNSIGNED NOT NULL,
    property_id                BIGINT UNSIGNED NOT NULL,
    message                    TEXT NOT NULL,
    status                     ENUM('OPEN', 'IN_PROGRESS', 'CLOSED') NOT NULL DEFAULT 'OPEN',
    confirmation_email_sent_at DATETIME NULL,
    handled_by_admin_id        BIGINT UNSIGNED NULL,
    created_at                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_property_inquiries_user (user_id),
    KEY idx_property_inquiries_property_status (property_id, status),
    KEY idx_property_inquiries_created_at (created_at),
    KEY idx_property_inquiries_admin (handled_by_admin_id),
    CONSTRAINT fk_property_inquiries_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_property_inquiries_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CONSTRAINT fk_property_inquiries_admin FOREIGN KEY (handled_by_admin_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS booking_requests (
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id              BIGINT UNSIGNED NOT NULL,
    property_id          BIGINT UNSIGNED NOT NULL,
    start_date           DATE NULL,
    end_date             DATE NULL,
    status               ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED') NOT NULL DEFAULT 'PENDING',
    note                 VARCHAR(500) NULL,
    handled_by_admin_id  BIGINT UNSIGNED NULL,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_booking_requests_user (user_id),
    KEY idx_booking_requests_property_status (property_id, status),
    KEY idx_booking_requests_admin (handled_by_admin_id),
    CONSTRAINT fk_booking_requests_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_booking_requests_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CONSTRAINT fk_booking_requests_admin FOREIGN KEY (handled_by_admin_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_booking_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- If a property is unavailable, user can subscribe for similar listings.
CREATE TABLE IF NOT EXISTS listing_alert_subscriptions (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id            BIGINT UNSIGNED NOT NULL,
    source_property_id BIGINT UNSIGNED NULL,
    category           ENUM('RESIDENTIAL', 'COMMERCIAL', 'RENTAL') NULL,
    location_city      VARCHAR(100) NULL,
    min_price          DECIMAL(12, 2) NULL,
    max_price          DECIMAL(12, 2) NULL,
    bedrooms_min       SMALLINT UNSIGNED NULL,
    is_active          TINYINT(1) NOT NULL DEFAULT 1,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_listing_alert_user_active (user_id, is_active),
    KEY idx_listing_alert_city_category (location_city, category),
    KEY idx_listing_alert_source_property (source_property_id),
    CONSTRAINT fk_listing_alert_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_listing_alert_source_property FOREIGN KEY (source_property_id) REFERENCES properties(id) ON DELETE SET NULL,
    CONSTRAINT chk_listing_alert_price_range CHECK (
        (min_price IS NULL OR min_price >= 0) AND
        (max_price IS NULL OR max_price >= 0) AND
        (min_price IS NULL OR max_price IS NULL OR min_price <= max_price)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS listing_alert_subscription_amenities (
    subscription_id BIGINT UNSIGNED NOT NULL,
    amenity_id      BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (subscription_id, amenity_id),
    KEY idx_listing_alert_subscription_amenity (amenity_id),
    CONSTRAINT fk_listing_alert_subscription FOREIGN KEY (subscription_id) REFERENCES listing_alert_subscriptions(id) ON DELETE CASCADE,
    CONSTRAINT fk_listing_alert_subscription_amenity FOREIGN KEY (amenity_id) REFERENCES amenities(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- PAYMENTS, EMAILS, SEARCH HISTORY, AND LOGS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS payments (
    id                         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id                    BIGINT UNSIGNED NOT NULL,
    related_booking_request_id BIGINT UNSIGNED NULL,
    payment_type               ENUM('PREMIUM_BOOKING_FEE', 'BOOKING_DEPOSIT', 'OTHER') NOT NULL DEFAULT 'PREMIUM_BOOKING_FEE',
    payment_method             ENUM('CREDIT_CARD', 'BANK_TRANSFER') NOT NULL,
    amount                     DECIMAL(12, 2) NOT NULL,
    currency                   CHAR(3) NOT NULL DEFAULT 'USD',
    status                     ENUM('PENDING', 'PAID', 'FAILED', 'REFUNDED') NOT NULL DEFAULT 'PENDING',
    external_reference         VARCHAR(120) NULL,
    paid_at                    DATETIME NULL,
    created_at                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_payments_user_created (user_id, created_at),
    KEY idx_payments_status (status),
    KEY idx_payments_booking_request (related_booking_request_id),
    CONSTRAINT fk_payments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_payments_booking_request FOREIGN KEY (related_booking_request_id) REFERENCES booking_requests(id) ON DELETE SET NULL,
    CONSTRAINT chk_payments_amount CHECK (amount >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS email_notifications (
    id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id               BIGINT UNSIGNED NULL,
    purpose               ENUM('LOGIN_2FA', 'VIEWING_CONFIRMATION', 'INQUIRY_CONFIRMATION', 'BOOKING_UPDATE', 'SIMILAR_LISTING_ALERT') NOT NULL,
    recipient_email       VARCHAR(255) NOT NULL,
    reference_type        VARCHAR(40) NULL,
    reference_id          BIGINT UNSIGNED NULL,
    status                ENUM('PENDING', 'SENT', 'FAILED') NOT NULL DEFAULT 'PENDING',
    delivery_requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at               DATETIME NULL,
    error_message         VARCHAR(300) NULL,
    PRIMARY KEY (id),
    KEY idx_email_notifications_user_status (user_id, status),
    KEY idx_email_notifications_purpose_created (purpose, delivery_requested_at),
    CONSTRAINT fk_email_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Stores search filters to support search trends in supervisor reports.
CREATE TABLE IF NOT EXISTS search_history (
    id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id               BIGINT UNSIGNED NULL,
    search_text           VARCHAR(255) NULL,
    location_city         VARCHAR(100) NULL,
    min_price             DECIMAL(12, 2) NULL,
    max_price             DECIMAL(12, 2) NULL,
    category              ENUM('RESIDENTIAL', 'COMMERCIAL', 'RENTAL') NULL,
    bedrooms_min          SMALLINT UNSIGNED NULL,
    amenities_filter_json JSON NULL,
    result_count          INT UNSIGNED NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_search_history_user_created (user_id, created_at),
    KEY idx_search_history_city_created (location_city, created_at),
    KEY idx_search_history_category_created (category, created_at),
    CONSTRAINT fk_search_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_search_history_price_range CHECK (
        (min_price IS NULL OR min_price >= 0) AND
        (max_price IS NULL OR max_price >= 0) AND
        (min_price IS NULL OR max_price IS NULL OR min_price <= max_price)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Generic audit log for interactions and transactions.
CREATE TABLE IF NOT EXISTS activity_logs (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     BIGINT UNSIGNED NULL,
    scope       ENUM('AUTH', 'INTERACTION', 'TRANSACTION', 'SYSTEM') NOT NULL,
    action      VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NULL,
    entity_id   BIGINT UNSIGNED NULL,
    metadata    JSON NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_activity_logs_created_at (created_at),
    KEY idx_activity_logs_user_created (user_id, created_at),
    KEY idx_activity_logs_scope_created (scope, created_at),
    CONSTRAINT fk_activity_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- REPORTING VIEWS FOR SUPERVISORS
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW vw_monthly_inquiries AS
SELECT
    DATE_FORMAT(created_at, '%Y-%m-01') AS month_start,
    COUNT(*) AS total_inquiries,
    SUM(status = 'OPEN') AS open_inquiries,
    SUM(status = 'CLOSED') AS closed_inquiries
FROM property_inquiries
GROUP BY DATE_FORMAT(created_at, '%Y-%m-01');

CREATE OR REPLACE VIEW vw_monthly_saved_properties AS
SELECT
    DATE_FORMAT(created_at, '%Y-%m-01') AS month_start,
    COUNT(*) AS total_saved_properties
FROM user_favorites
GROUP BY DATE_FORMAT(created_at, '%Y-%m-01');

CREATE OR REPLACE VIEW vw_monthly_search_trends AS
SELECT
    DATE_FORMAT(created_at, '%Y-%m-01') AS month_start,
    COALESCE(location_city, 'UNKNOWN') AS location_city,
    COALESCE(category, 'ALL') AS category,
    COUNT(*) AS total_searches
FROM search_history
GROUP BY
    DATE_FORMAT(created_at, '%Y-%m-01'),
    COALESCE(location_city, 'UNKNOWN'),
    COALESCE(category, 'ALL');

-- ------------------------------------------------------------
-- OPTIONAL CLEANUP EVENT (3-MONTH LOG RETENTION)
-- ------------------------------------------------------------
-- Before enabling this event, make sure MySQL event scheduler is ON:
-- SET GLOBAL event_scheduler = ON;

CREATE EVENT IF NOT EXISTS ev_cleanup_activity_logs_90_days
ON SCHEDULE EVERY 1 DAY
DO
  DELETE FROM activity_logs
  WHERE created_at < (UTC_TIMESTAMP() - INTERVAL 90 DAY);
