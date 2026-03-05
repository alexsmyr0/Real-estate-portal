SET NAMES utf8mb4;
SET time_zone = '+00:00';

START TRANSACTION;

-- ------------------------------------------------------------
-- USERS
-- 1 admin, 1 supervisor, 2 regular users
-- ------------------------------------------------------------

INSERT INTO users (
    email, password_hash, full_name, phone, role, is_active, email_verified_at, gdpr_consent_at
)
SELECT
    'admin@homefinder.local',
    'demo_hash_admin',
    'Admin User',
    '+1-555-0001',
    'ADMIN',
    1,
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'admin@homefinder.local'
);

INSERT INTO users (
    email, password_hash, full_name, phone, role, is_active, email_verified_at, gdpr_consent_at
)
SELECT
    'supervisor@homefinder.local',
    'demo_hash_supervisor',
    'Supervisor User',
    '+1-555-0002',
    'SUPERVISOR',
    1,
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'supervisor@homefinder.local'
);

INSERT INTO users (
    email, password_hash, full_name, phone, role, is_active, email_verified_at, gdpr_consent_at
)
SELECT
    'user1@homefinder.local',
    'demo_hash_user1',
    'User One',
    '+1-555-0003',
    'USER',
    1,
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'user1@homefinder.local'
);

INSERT INTO users (
    email, password_hash, full_name, phone, role, is_active, email_verified_at, gdpr_consent_at
)
SELECT
    'user2@homefinder.local',
    'demo_hash_user2',
    'User Two',
    '+1-555-0004',
    'USER',
    1,
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'user2@homefinder.local'
);

SET @admin_id = (SELECT id FROM users WHERE email = 'admin@homefinder.local' LIMIT 1);
SET @user1_id = (SELECT id FROM users WHERE email = 'user1@homefinder.local' LIMIT 1);
SET @user2_id = (SELECT id FROM users WHERE email = 'user2@homefinder.local' LIMIT 1);

-- ------------------------------------------------------------
-- PROPERTIES
-- 3 properties listed by admin
-- ------------------------------------------------------------

INSERT INTO properties (
    title, description, category, status, city, area, address_line, price,
    bedrooms, bathrooms, listed_by_id
)
SELECT
    'Modern Family House',
    'Spacious residential home with garden.',
    'RESIDENTIAL',
    'AVAILABLE',
    'Athens',
    'Chalandri',
    '12 Green Street',
    245000.00,
    3,
    2.0,
    @admin_id
WHERE @admin_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM properties
      WHERE title = 'Modern Family House' AND city = 'Athens'
  );

INSERT INTO properties (
    title, description, category, status, city, area, address_line, price,
    bedrooms, bathrooms, listed_by_id
)
SELECT
    'Downtown Office Space',
    'Commercial office close to transit and services.',
    'COMMERCIAL',
    'AVAILABLE',
    'Athens',
    'Syntagma',
    '22 Business Ave',
    520000.00,
    NULL,
    2.0,
    @admin_id
WHERE @admin_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM properties
      WHERE title = 'Downtown Office Space' AND city = 'Athens'
  );

INSERT INTO properties (
    title, description, category, status, city, area, address_line, price,
    bedrooms, bathrooms, listed_by_id
)
SELECT
    'City Rental Apartment',
    'Rental apartment suitable for students.',
    'RENTAL',
    'UNAVAILABLE',
    'Athens',
    'Exarchia',
    '7 Student Road',
    850.00,
    2,
    1.0,
    @admin_id
WHERE @admin_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM properties
      WHERE title = 'City Rental Apartment' AND city = 'Athens'
  );

SET @property1_id = (
    SELECT id FROM properties
    WHERE title = 'Modern Family House' AND city = 'Athens'
    LIMIT 1
);
SET @property2_id = (
    SELECT id FROM properties
    WHERE title = 'Downtown Office Space' AND city = 'Athens'
    LIMIT 1
);
SET @property3_id = (
    SELECT id FROM properties
    WHERE title = 'City Rental Apartment' AND city = 'Athens'
    LIMIT 1
);

-- ------------------------------------------------------------
-- FAVORITES
-- ------------------------------------------------------------

INSERT IGNORE INTO user_favorites (user_id, property_id, created_at)
SELECT @user1_id, @property1_id, UTC_TIMESTAMP()
WHERE @user1_id IS NOT NULL AND @property1_id IS NOT NULL;

INSERT IGNORE INTO user_favorites (user_id, property_id, created_at)
SELECT @user1_id, @property2_id, UTC_TIMESTAMP()
WHERE @user1_id IS NOT NULL AND @property2_id IS NOT NULL;

INSERT IGNORE INTO user_favorites (user_id, property_id, created_at)
SELECT @user2_id, @property1_id, UTC_TIMESTAMP()
WHERE @user2_id IS NOT NULL AND @property1_id IS NOT NULL;

-- ------------------------------------------------------------
-- INQUIRIES
-- ------------------------------------------------------------

INSERT INTO property_inquiries (
    user_id, property_id, message, status, created_at, updated_at
)
SELECT
    @user1_id,
    @property1_id,
    'Is this property still available and can I schedule a visit this week?',
    'OPEN',
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE @user1_id IS NOT NULL
  AND @property1_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM property_inquiries
      WHERE user_id = @user1_id
        AND property_id = @property1_id
        AND message = 'Is this property still available and can I schedule a visit this week?'
  );

INSERT INTO property_inquiries (
    user_id, property_id, message, status, created_at, updated_at
)
SELECT
    @user2_id,
    @property2_id,
    'Can you share maintenance costs and utility details?',
    'IN_PROGRESS',
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE @user2_id IS NOT NULL
  AND @property2_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM property_inquiries
      WHERE user_id = @user2_id
        AND property_id = @property2_id
        AND message = 'Can you share maintenance costs and utility details?'
  );

-- ------------------------------------------------------------
-- BOOKING REQUESTS
-- ------------------------------------------------------------

INSERT INTO booking_requests (
    user_id, property_id, start_date, end_date, status, note, created_at, updated_at
)
SELECT
    @user1_id,
    @property3_id,
    DATE_ADD(UTC_DATE(), INTERVAL 14 DAY),
    DATE_ADD(UTC_DATE(), INTERVAL 20 DAY),
    'PENDING',
    'Interested in short-term rent for one week.',
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE @user1_id IS NOT NULL
  AND @property3_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM booking_requests
      WHERE user_id = @user1_id
        AND property_id = @property3_id
        AND start_date = DATE_ADD(UTC_DATE(), INTERVAL 14 DAY)
        AND end_date = DATE_ADD(UTC_DATE(), INTERVAL 20 DAY)
  );

INSERT INTO booking_requests (
    user_id, property_id, start_date, end_date, status, note, created_at, updated_at
)
SELECT
    @user2_id,
    @property1_id,
    DATE_ADD(UTC_DATE(), INTERVAL 30 DAY),
    DATE_ADD(UTC_DATE(), INTERVAL 37 DAY),
    'APPROVED',
    'Family visit planned next month.',
    UTC_TIMESTAMP(),
    UTC_TIMESTAMP()
WHERE @user2_id IS NOT NULL
  AND @property1_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM booking_requests
      WHERE user_id = @user2_id
        AND property_id = @property1_id
        AND start_date = DATE_ADD(UTC_DATE(), INTERVAL 30 DAY)
        AND end_date = DATE_ADD(UTC_DATE(), INTERVAL 37 DAY)
  );

COMMIT;
