# Design and Development of HomeFinder Portal

## 1. System Context

HomeFinder is an online real estate portal designed to provide a seamless property search experience.  
The system enables users to browse, search, select, and inquire about residential and commercial properties efficiently.

HomeFinder (hereafter referred to as the **system**) aims to:
- streamline property discovery,
- support personalized recommendations,
- increase user engagement.

### 1.1 User Management and System Access

- Users must register with an email address and secure password.
- Login requires credentials (email and password) plus a two-factor authentication token sent via email within 30 seconds.
- To safeguard personal data, the system follows GDPR principles and collects only essential information.
- Only one active session per user is allowed at a time to reduce account misuse.

### 1.2 Property Search, Reservation, and Inquiry

- Users can browse properties in the categories: residential, commercial, and rental.
- Filters include location, price range, property type, bedrooms, and amenities.
- Users can save properties to favorites, remove listings, or schedule viewings.
- Confirmation emails are sent for viewings and inquiries.
- Inquiries and booking requests can be submitted directly through the portal.
- If a property is unavailable, users can subscribe to notifications for similar listings.

### 1.3 Supervision and Management

- Two manager roles exist: **Customer Service Supervisors** and **Admins**.
- Supervisors can access monthly reports (inquiries, saved properties, and search trends).
- Admins can add and update property listings and manage user interactions.
- Payment options include credit card, bank transfer, and booking fees for premium services.
- All transactions and interactions are logged for analysis, with logs retained for 3 months.

## 2. System Characteristics

- Operates as a web client with secure server-side data storage.
- Supports scheduled weekly downtime of up to 30 minutes for maintenance.
- Includes future support plans for a mobile application.
- Maintains detailed activity logs for searches, inquiries, and saved properties.
