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
    gdpr_consent_at   DATETIME NULL,
    deleted_at        DATETIME NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_email (email),
    KEY idx_users_role (role),
    KEY idx_users_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Use login_2fa_tokens instead of 2fa_tokens (MySQL identifiers should not start with number).
CREATE TABLE IF NOT EXISTS login_2fa_tokens (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id       BIGINT UNSIGNED NOT NULL,
    token_hash    CHAR(64) NOT NULL,
    sent_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    DATETIME NOT NULL,
    verified_at   DATETIME NULL,
    attempts_used SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_2fa_user_status (user_id, verified_at, expires_at),
    CONSTRAINT fk_2fa_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- One active session per user (PRIMARY KEY user_id enforces one row per user).
CREATE TABLE IF NOT EXISTS active_sessions (
    user_id            BIGINT UNSIGNED NOT NULL,
    session_token_hash CHAR(64) NOT NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at         DATETIME NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE KEY uk_active_sessions_token_hash (session_token_hash),
    CONSTRAINT fk_active_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- PROPERTIES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS properties (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title         VARCHAR(200) NOT NULL,
    description   TEXT NULL,
    category      ENUM('RESIDENTIAL', 'COMMERCIAL', 'RENTAL') NOT NULL,
    status        ENUM('AVAILABLE', 'UNAVAILABLE', 'REMOVED') NOT NULL DEFAULT 'AVAILABLE',
    city          VARCHAR(100) NOT NULL,
    area          VARCHAR(120) NULL,
    address_line  VARCHAR(255) NULL,
    price         DECIMAL(12, 2) NOT NULL,
    bedrooms      SMALLINT UNSIGNED NULL,
    bathrooms     DECIMAL(3, 1) NULL,
    listed_by_id  BIGINT UNSIGNED NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_properties_category_status (category, status),
    KEY idx_properties_city (city),
    KEY idx_properties_price (price),
    KEY idx_properties_search_filters (city, category, status, price, bedrooms),
    CONSTRAINT fk_properties_admin FOREIGN KEY (listed_by_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS amenities (
    id   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_amenities_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS property_amenities (
    property_id BIGINT UNSIGNED NOT NULL,
    amenity_id  BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (property_id, amenity_id),
    KEY idx_property_amenities_amenity (amenity_id),
    CONSTRAINT fk_property_amenities_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CONSTRAINT fk_property_amenities_amenity FOREIGN KEY (amenity_id) REFERENCES amenities(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS property_images (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    property_id BIGINT UNSIGNED NOT NULL,
    image_url   VARCHAR(500) NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
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
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id            BIGINT UNSIGNED NOT NULL,
    property_id        BIGINT UNSIGNED NOT NULL,
    requested_datetime DATETIME NOT NULL,
    status             ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED') NOT NULL DEFAULT 'PENDING',
    note               VARCHAR(500) NULL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_viewing_requests_user (user_id),
    KEY idx_viewing_requests_property (property_id),
    CONSTRAINT fk_viewing_requests_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_viewing_requests_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS property_inquiries (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     BIGINT UNSIGNED NOT NULL,
    property_id BIGINT UNSIGNED NOT NULL,
    message     TEXT NOT NULL,
    status      ENUM('OPEN', 'IN_PROGRESS', 'CLOSED') NOT NULL DEFAULT 'OPEN',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_property_inquiries_user (user_id),
    KEY idx_property_inquiries_property (property_id),
    CONSTRAINT fk_property_inquiries_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_property_inquiries_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS booking_requests (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     BIGINT UNSIGNED NOT NULL,
    property_id BIGINT UNSIGNED NOT NULL,
    start_date  DATE NULL,
    end_date    DATE NULL,
    status      ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED') NOT NULL DEFAULT 'PENDING',
    note        VARCHAR(500) NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_booking_requests_user (user_id),
    KEY idx_booking_requests_property (property_id),
    CONSTRAINT fk_booking_requests_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_booking_requests_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- If property is unavailable, users can subscribe for similar listings.
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
    PRIMARY KEY (id),
    KEY idx_listing_alert_user_active (user_id, is_active),
    KEY idx_listing_alert_source_property (source_property_id),
    KEY idx_alert_active_category_city (is_active, category, location_city),
    KEY idx_alert_price_range (min_price, max_price),
    KEY idx_alert_bedrooms_min (bedrooms_min),
    CONSTRAINT fk_listing_alert_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_listing_alert_source_property FOREIGN KEY (source_property_id) REFERENCES properties(id) ON DELETE SET NULL,
    CONSTRAINT ck_alert_price_bounds CHECK (min_price IS NULL OR max_price IS NULL OR min_price <= max_price),
    CONSTRAINT ck_alert_bedrooms_min_positive CHECK (bedrooms_min IS NULL OR bedrooms_min > 0),
    CONSTRAINT ck_active_alert_has_source_property CHECK (is_active = 0 OR source_property_id IS NOT NULL),
    CONSTRAINT ck_active_alert_has_required_filters CHECK (is_active = 0 OR (category <> '' AND location_city <> ''))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS listing_alert_subscription_amenities (
    subscription_id BIGINT UNSIGNED NOT NULL,
    amenity_id      BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (subscription_id, amenity_id),
    KEY idx_listing_alert_subscription_amenity (amenity_id),
    CONSTRAINT fk_listing_alert_subscription FOREIGN KEY (subscription_id) REFERENCES listing_alert_subscriptions(id) ON DELETE CASCADE,
    CONSTRAINT fk_listing_alert_subscription_amenity FOREIGN KEY (amenity_id) REFERENCES amenities(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- PAYMENTS, NOTIFICATIONS, SEARCH HISTORY, LOGS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS payments (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id            BIGINT UNSIGNED NOT NULL,
    booking_request_id BIGINT UNSIGNED NULL,
    payment_purpose    ENUM('BOOKING_FEE', 'PREMIUM_SERVICE', 'OTHER') NOT NULL DEFAULT 'OTHER',
    payment_method     ENUM('CREDIT_CARD', 'BANK_TRANSFER') NOT NULL,
    amount             DECIMAL(12, 2) NOT NULL,
    status             ENUM('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED') NOT NULL DEFAULT 'PENDING',
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_payments_user_created (user_id, created_at),
    CONSTRAINT fk_payments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_payments_booking_request FOREIGN KEY (booking_request_id) REFERENCES booking_requests(id) ON DELETE RESTRICT,
    CONSTRAINT ck_payment_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_payment_booking_fee_has_booking CHECK (payment_purpose <> 'BOOKING_FEE' OR booking_request_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS email_notifications (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         BIGINT UNSIGNED NULL,
    purpose         ENUM('LOGIN_2FA', 'VIEWING_CONFIRMATION', 'INQUIRY_CONFIRMATION', 'BOOKING_UPDATE', 'SIMILAR_LISTING_ALERT') NOT NULL,
    recipient_email VARCHAR(255) NOT NULL,
    status          ENUM('PENDING', 'SENT', 'FAILED') NOT NULL DEFAULT 'PENDING',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at         DATETIME NULL,
    PRIMARY KEY (id),
    KEY idx_email_notifications_user_status (user_id, status),
    CONSTRAINT fk_email_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS similar_listing_alert_dispatches (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    subscription_id BIGINT UNSIGNED NOT NULL,
    property_id     BIGINT UNSIGNED NOT NULL,
    notification_id BIGINT UNSIGNED NULL,
    status          ENUM('PENDING', 'SENT', 'FAILED') NOT NULL DEFAULT 'PENDING',
    attempt_count   INT UNSIGNED NOT NULL DEFAULT 0,
    last_attempted_at DATETIME NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_similar_listing_alert_dispatch (subscription_id, property_id),
    UNIQUE KEY uq_similar_listing_alert_notification (notification_id),
    KEY idx_similar_listing_alert_property (property_id),
    KEY idx_similar_alert_pair_status (subscription_id, property_id, status),
    KEY idx_sim_alert_status_updated (status, updated_at),
    CONSTRAINT fk_similar_listing_alert_subscription FOREIGN KEY (subscription_id) REFERENCES listing_alert_subscriptions(id) ON DELETE CASCADE,
    CONSTRAINT fk_similar_listing_alert_property FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
    CONSTRAINT fk_similar_listing_alert_notification FOREIGN KEY (notification_id) REFERENCES email_notifications(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS search_history (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id       BIGINT UNSIGNED NULL,
    location_city VARCHAR(100) NULL,
    min_price     DECIMAL(12, 2) NULL,
    max_price     DECIMAL(12, 2) NULL,
    category      ENUM('RESIDENTIAL', 'COMMERCIAL', 'RENTAL') NULL,
    bedrooms_min  SMALLINT UNSIGNED NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_search_history_user_created (user_id, created_at),
    CONSTRAINT fk_search_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS activity_logs (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id    BIGINT UNSIGNED NULL,
    scope      ENUM('AUTH', 'SEARCH', 'INTERACTION', 'TRANSACTION', 'SYSTEM') NOT NULL,
    action     VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NULL,
    entity_id  BIGINT UNSIGNED NULL,
    details    JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_activity_logs_created_at (created_at),
    KEY idx_activity_logs_user_created (user_id, created_at),
    CONSTRAINT fk_activity_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Log retention policy (3 months). Requires MySQL event scheduler to be enabled:
-- SET GLOBAL event_scheduler = ON;
CREATE EVENT IF NOT EXISTS ev_purge_activity_logs_3_months
ON SCHEDULE EVERY 1 DAY
DO
  DELETE FROM activity_logs
  WHERE created_at < (UTC_TIMESTAMP() - INTERVAL 3 MONTH);
