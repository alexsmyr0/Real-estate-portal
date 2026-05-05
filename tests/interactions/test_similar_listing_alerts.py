from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from homefinder.apps.interactions.models import (
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    SimilarListingAlertDispatch,
    SimilarListingAlertDispatchStatus,
)
from homefinder.apps.interactions.services import EmailNotificationMessage, EmailNotificationService
from homefinder.apps.properties.models import (
    Amenity,
    ListingAlertSubscription,
    Property,
    PropertyCategory,
    PropertyStatus,
)
from homefinder.apps.properties.services import (
    create_listing_alert_subscription,
    dispatch_similar_listing_alerts,
    listing_matches_alert_subscription,
    matching_listing_alert_subscriptions,
    set_listing_alert_subscription_active,
)
from homefinder.apps.users.models import User


class RecordingDeliveryAdapter:
    def __init__(self, *, delivered_count: int = 1, exception: Exception | None = None) -> None:
        self.delivered_count = delivered_count
        self.exception = exception
        self.messages: list[EmailNotificationMessage] = []

    def deliver(self, message: EmailNotificationMessage) -> int:
        self.messages.append(message)
        if self.exception:
            raise self.exception
        return self.delivered_count


class SimilarListingAlertTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="secret-pass",
            full_name="Buyer Example",
        )
        self.pool = Amenity.objects.create(name="Pool")
        self.gym = Amenity.objects.create(name="Gym")
        self.parking = Amenity.objects.create(name="Parking")
        self.source_property = self._property(
            title="Unavailable Athens Apartment",
            status=PropertyStatus.UNAVAILABLE,
            category=PropertyCategory.RESIDENTIAL,
            city="Athens",
            price="250000.00",
            bedrooms=2,
        )
        self.source_property.amenities.add(self.pool, self.gym)

    def test_subscription_persistence_stores_unavailable_source_criteria_and_amenities(self) -> None:
        subscription = create_listing_alert_subscription(
            user=self.user,
            source_property=self.source_property,
            min_price=Decimal("200000.00"),
            max_price=Decimal("280000.00"),
        )

        subscription.refresh_from_db()
        self.assertEqual(ListingAlertSubscription.objects.count(), 1)
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.source_property, self.source_property)
        self.assertEqual(subscription.category, PropertyCategory.RESIDENTIAL)
        self.assertEqual(subscription.location_city, "Athens")
        self.assertEqual(subscription.min_price, Decimal("200000.00"))
        self.assertEqual(subscription.max_price, Decimal("280000.00"))
        self.assertEqual(subscription.bedrooms_min, 2)
        self.assertTrue(subscription.is_active)
        self.assertEqual(set(subscription.amenities.values_list("id", flat=True)), {self.pool.id, self.gym.id})

    def test_subscription_creation_rejects_available_source_property(self) -> None:
        available_source = self._property(title="Available Source", status=PropertyStatus.AVAILABLE)

        with self.assertRaises(ValidationError):
            create_listing_alert_subscription(user=self.user, source_property=available_source)

        self.assertEqual(ListingAlertSubscription.objects.count(), 0)

    def test_direct_model_save_rejects_active_subscription_with_available_source_property(self) -> None:
        available_source = self._property(title="Available Source", status=PropertyStatus.AVAILABLE)
        subscription = ListingAlertSubscription(
            user=self.user,
            source_property=available_source,
            category=PropertyCategory.RESIDENTIAL,
            location_city="Athens",
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            subscription.save()

        self.assertEqual(ListingAlertSubscription.objects.count(), 0)

    def test_direct_model_save_rejects_active_subscription_with_removed_source_property(self) -> None:
        removed_source = self._property(title="Removed Source", status=PropertyStatus.REMOVED)
        subscription = ListingAlertSubscription(
            user=self.user,
            source_property=removed_source,
            category=PropertyCategory.RESIDENTIAL,
            location_city="Athens",
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            subscription.save()

        self.assertEqual(ListingAlertSubscription.objects.count(), 0)

    def test_direct_model_save_accepts_active_subscription_with_unavailable_source_property(self) -> None:
        subscription = ListingAlertSubscription(
            user=self.user,
            source_property=self.source_property,
            category=PropertyCategory.RESIDENTIAL,
            location_city="Athens",
            is_active=True,
        )

        subscription.save()

        self.assertEqual(ListingAlertSubscription.objects.get(), subscription)

    def test_manager_create_cannot_bypass_active_source_property_validation(self) -> None:
        available_source = self._property(title="Available Source", status=PropertyStatus.AVAILABLE)

        with self.assertRaises(ValidationError):
            ListingAlertSubscription.objects.create(
                user=self.user,
                source_property=available_source,
                category=PropertyCategory.RESIDENTIAL,
                location_city="Athens",
                is_active=True,
            )

        self.assertEqual(ListingAlertSubscription.objects.count(), 0)

    def test_active_subscription_model_validation_rejects_missing_required_criteria(self) -> None:
        invalid_subscriptions = (
            ListingAlertSubscription(user=self.user, is_active=True),
            ListingAlertSubscription(
                user=self.user,
                source_property=self.source_property,
                category="",
                location_city="Athens",
                is_active=True,
            ),
            ListingAlertSubscription(
                user=self.user,
                source_property=self.source_property,
                category=PropertyCategory.RESIDENTIAL,
                location_city="",
                is_active=True,
            ),
            ListingAlertSubscription(
                user=self.user,
                source_property=self.source_property,
                category=PropertyCategory.RESIDENTIAL,
                location_city="Athens",
                min_price=Decimal("300000.00"),
                max_price=Decimal("200000.00"),
                is_active=True,
            ),
            ListingAlertSubscription(
                user=self.user,
                source_property=self.source_property,
                category=PropertyCategory.RESIDENTIAL,
                location_city="Athens",
                bedrooms_min=0,
                is_active=True,
            ),
        )

        for subscription in invalid_subscriptions:
            with self.subTest(subscription=subscription):
                with self.assertRaises(ValidationError):
                    subscription.save()

        self.assertEqual(ListingAlertSubscription.objects.count(), 0)

    def test_model_validation_allows_valid_active_and_minimal_inactive_subscriptions(self) -> None:
        available_source = self._property(title="Inactive Available Source", status=PropertyStatus.AVAILABLE)
        active_subscription = ListingAlertSubscription.objects.create(
            user=self.user,
            source_property=self.source_property,
            category=PropertyCategory.RESIDENTIAL,
            location_city="Athens",
            min_price=Decimal("200000.00"),
            max_price=Decimal("280000.00"),
            bedrooms_min=2,
            is_active=True,
        )
        inactive_subscription = ListingAlertSubscription.objects.create(user=self.user, is_active=False)
        inactive_with_available_source = ListingAlertSubscription.objects.create(
            user=self.user,
            source_property=available_source,
            is_active=False,
        )

        self.assertTrue(active_subscription.is_active)
        self.assertFalse(inactive_subscription.is_active)
        self.assertFalse(inactive_with_available_source.is_active)
        self.assertEqual(ListingAlertSubscription.objects.count(), 3)

    def test_subscription_lifecycle_state_blocks_matching(self) -> None:
        subscription = self._subscription()
        listing = self._matching_listing()

        self.assertTrue(listing_matches_alert_subscription(subscription, listing))

        set_listing_alert_subscription_active(subscription, is_active=False)
        subscription.refresh_from_db()

        self.assertFalse(subscription.is_active)
        self.assertFalse(listing_matches_alert_subscription(subscription, listing))
        self.assertEqual(dispatch_similar_listing_alerts(listing), [])

    def test_matching_success_allows_amenity_overlap(self) -> None:
        subscription = self._subscription(amenity_ids=[self.pool.id, self.gym.id])
        listing = self._matching_listing(amenities=[self.pool])

        self.assertTrue(listing_matches_alert_subscription(subscription, listing))
        self.assertEqual(matching_listing_alert_subscriptions(listing), [subscription])

    def test_subscription_without_amenities_matches_without_overlap_requirement(self) -> None:
        subscription = self._subscription(amenity_ids=[])
        listing = self._matching_listing(amenities=[])

        self.assertTrue(listing_matches_alert_subscription(subscription, listing))
        self.assertEqual(matching_listing_alert_subscriptions(listing), [subscription])

    def test_database_matching_rejects_subscription_with_no_amenity_overlap(self) -> None:
        self._subscription(amenity_ids=[self.pool.id, self.gym.id])
        listing = self._matching_listing(amenities=[self.parking])

        self.assertEqual(matching_listing_alert_subscriptions(listing), [])

    def test_matching_rejects_non_qualifying_listings(self) -> None:
        cases = {
            "wrong category": self._matching_listing(category=PropertyCategory.COMMERCIAL),
            "wrong city": self._matching_listing(city="Patra"),
            "outside price range": self._matching_listing(price="300000.00"),
            "below bedroom minimum": self._matching_listing(bedrooms=1),
            "no sufficient amenity overlap": self._matching_listing(amenities=[self.parking]),
        }

        for case_name, listing in cases.items():
            with self.subTest(case=case_name):
                subscription = self._subscription(amenity_ids=[self.pool.id, self.gym.id])
                self.assertFalse(listing_matches_alert_subscription(subscription, listing))

        inactive_subscription = self._subscription(amenity_ids=[self.pool.id])
        set_listing_alert_subscription_active(inactive_subscription, is_active=False)
        with self.subTest(case="inactive subscription"):
            self.assertFalse(listing_matches_alert_subscription(inactive_subscription, self._matching_listing()))

    def test_alert_dispatch_creates_notification_through_shared_email_service(self) -> None:
        self._subscription()
        listing = self._matching_listing()
        adapter = RecordingDeliveryAdapter()
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.captureOnCommitCallbacks(execute=True):
            dispatches = dispatch_similar_listing_alerts(listing, notification_service=service)

        self.assertEqual(len(dispatches), 1)
        self.assertEqual(SimilarListingAlertDispatch.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)

        notification = EmailNotification.objects.get()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.SIMILAR_LISTING_ALERT)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertEqual(dispatches[0].notification, notification)
        dispatches[0].refresh_from_db()
        self.assertEqual(dispatches[0].status, SimilarListingAlertDispatchStatus.SENT)
        self.assertEqual(dispatches[0].attempt_count, 1)
        self.assertEqual(len(adapter.messages), 1)
        self.assertEqual(adapter.messages[0].purpose, EmailNotificationPurpose.SIMILAR_LISTING_ALERT)
        self.assertIn(listing.title, adapter.messages[0].body)

    def test_failed_alert_delivery_does_not_block_retry_and_later_success(self) -> None:
        self._subscription()
        listing = self._matching_listing()
        failing_service = EmailNotificationService(
            delivery_adapter=RecordingDeliveryAdapter(exception=RuntimeError("email temporarily unavailable"))
        )

        with self.assertLogs("homefinder.apps.interactions.services", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                failed_dispatches = dispatch_similar_listing_alerts(listing, notification_service=failing_service)

        failed_dispatch = failed_dispatches[0]
        failed_dispatch.refresh_from_db()
        self.assertEqual(failed_dispatch.status, SimilarListingAlertDispatchStatus.FAILED)
        self.assertEqual(failed_dispatch.attempt_count, 1)
        self.assertEqual(EmailNotification.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.get().status, EmailNotificationStatus.FAILED)

        successful_adapter = RecordingDeliveryAdapter()
        successful_service = EmailNotificationService(delivery_adapter=successful_adapter)
        with self.captureOnCommitCallbacks(execute=True):
            retry_dispatches = dispatch_similar_listing_alerts(listing, notification_service=successful_service)

        self.assertEqual(len(retry_dispatches), 1)
        retry_dispatch = retry_dispatches[0]
        retry_dispatch.refresh_from_db()
        self.assertEqual(retry_dispatch.pk, failed_dispatch.pk)
        self.assertEqual(retry_dispatch.status, SimilarListingAlertDispatchStatus.SENT)
        self.assertEqual(retry_dispatch.attempt_count, 2)
        self.assertEqual(EmailNotification.objects.count(), 2)
        self.assertEqual(EmailNotification.objects.order_by("-created_at").first().status, EmailNotificationStatus.SENT)
        self.assertEqual(len(successful_adapter.messages), 1)

    def test_duplicate_dispatch_is_prevented_for_same_subscription_and_listing(self) -> None:
        self._subscription()
        listing = self._matching_listing()
        adapter = RecordingDeliveryAdapter()
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.captureOnCommitCallbacks(execute=True):
            first_dispatches = dispatch_similar_listing_alerts(listing, notification_service=service)
        with self.captureOnCommitCallbacks(execute=True):
            second_dispatches = dispatch_similar_listing_alerts(listing, notification_service=service)

        self.assertEqual(len(first_dispatches), 1)
        self.assertEqual(second_dispatches, [])
        self.assertEqual(SimilarListingAlertDispatch.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)
        self.assertEqual(len(adapter.messages), 1)

    def test_pending_dispatch_prevents_concurrent_duplicate_attempt(self) -> None:
        subscription = self._subscription()
        listing = self._matching_listing()
        SimilarListingAlertDispatch.objects.create(
            subscription=subscription,
            property=listing,
            status=SimilarListingAlertDispatchStatus.PENDING,
        )
        adapter = RecordingDeliveryAdapter()
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.captureOnCommitCallbacks(execute=True):
            dispatches = dispatch_similar_listing_alerts(listing, notification_service=service)

        self.assertEqual(dispatches, [])
        self.assertEqual(EmailNotification.objects.count(), 0)
        self.assertEqual(len(adapter.messages), 0)

    def test_available_listing_creation_schedules_alert_dispatch(self) -> None:
        with patch("homefinder.apps.properties.signals.dispatch_similar_listing_alerts") as dispatcher:
            with self.captureOnCommitCallbacks(execute=True):
                listing = self._property(title="Fresh Available Listing", status=PropertyStatus.AVAILABLE)

        dispatcher.assert_called_once()
        self.assertEqual(dispatcher.call_args.args[0].pk, listing.pk)

    def test_status_transition_to_available_schedules_alert_dispatch_once(self) -> None:
        for starting_status in (PropertyStatus.UNAVAILABLE, PropertyStatus.REMOVED):
            with self.subTest(starting_status=starting_status):
                listing = self._property(title=f"{starting_status} Listing", status=starting_status)

                with patch("homefinder.apps.properties.signals.dispatch_similar_listing_alerts") as dispatcher:
                    with self.captureOnCommitCallbacks(execute=True):
                        listing.status = PropertyStatus.AVAILABLE
                        listing.save(update_fields=["status"])

                dispatcher.assert_called_once()
                self.assertEqual(dispatcher.call_args.args[0].pk, listing.pk)

    def test_unrelated_update_to_available_listing_does_not_schedule_alert_dispatch(self) -> None:
        listing = self._property(title="Already Available Listing", status=PropertyStatus.AVAILABLE)

        with patch("homefinder.apps.properties.signals.dispatch_similar_listing_alerts") as dispatcher:
            with self.captureOnCommitCallbacks(execute=True):
                listing.description = "Updated description only."
                listing.save(update_fields=["description"])

        dispatcher.assert_not_called()

    def test_available_listing_material_matching_field_changes_schedule_alert_dispatch(self) -> None:
        cases = (
            ("category", PropertyCategory.COMMERCIAL),
            ("city", "Patra"),
            ("price", Decimal("260000.00")),
            ("bedrooms", 3),
        )

        for field_name, new_value in cases:
            with self.subTest(field=field_name):
                listing = self._property(title=f"{field_name} Change Listing", status=PropertyStatus.AVAILABLE)

                with patch("homefinder.apps.properties.signals.dispatch_similar_listing_alerts") as dispatcher:
                    with self.captureOnCommitCallbacks(execute=True):
                        setattr(listing, field_name, new_value)
                        listing.save(update_fields=[field_name])

                dispatcher.assert_called_once()
                self.assertEqual(dispatcher.call_args.args[0].pk, listing.pk)

    def test_available_listing_unchanged_material_field_does_not_schedule_alert_dispatch(self) -> None:
        listing = self._property(title="Unchanged Material Listing", status=PropertyStatus.AVAILABLE)

        with patch("homefinder.apps.properties.signals.dispatch_similar_listing_alerts") as dispatcher:
            with self.captureOnCommitCallbacks(execute=True):
                listing.price = listing.price
                listing.save(update_fields=["price"])

        dispatcher.assert_not_called()

    def test_listing_amenity_change_schedules_alert_dispatch(self) -> None:
        listing = self._property(title="Fresh Available Listing", status=PropertyStatus.AVAILABLE)

        with patch("homefinder.apps.properties.signals.dispatch_similar_listing_alerts") as dispatcher:
            with self.captureOnCommitCallbacks(execute=True):
                listing.amenities.add(self.pool)

        dispatcher.assert_called_once()
        self.assertEqual(dispatcher.call_args.args[0].pk, listing.pk)

    def test_unavailable_listing_amenity_change_does_not_schedule_alert_dispatch(self) -> None:
        listing = self._property(title="Unavailable Listing", status=PropertyStatus.UNAVAILABLE)

        with patch("homefinder.apps.properties.signals.dispatch_similar_listing_alerts") as dispatcher:
            with self.captureOnCommitCallbacks(execute=True):
                listing.amenities.add(self.pool)

        dispatcher.assert_not_called()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_duplicate_save_and_amenity_scheduling_is_idempotent(self) -> None:
        self._subscription(amenity_ids=[])

        with self.captureOnCommitCallbacks(execute=True):
            listing = self._property(title="Fresh Available Listing", status=PropertyStatus.AVAILABLE)
            listing.amenities.add(self.pool)

        self.assertEqual(SimilarListingAlertDispatch.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)
        dispatch = SimilarListingAlertDispatch.objects.get(property=listing)
        self.assertEqual(dispatch.status, SimilarListingAlertDispatchStatus.SENT)

    def test_no_frontend_or_ui_routes_are_added_for_alert_subscriptions(self) -> None:
        from homefinder.apps.properties.urls import urlpatterns

        route_names = {pattern.name for pattern in urlpatterns}

        self.assertNotIn("listing-alert-subscribe", route_names)
        self.assertNotIn("similar-listing-alerts", route_names)
        self.assertTrue(all("alert" not in (route_name or "") for route_name in route_names))

    def _subscription(
        self,
        *,
        amenity_ids: list[int] | None = None,
    ) -> ListingAlertSubscription:
        return create_listing_alert_subscription(
            user=self.user,
            source_property=self.source_property,
            min_price="200000.00",
            max_price="280000.00",
            bedrooms_min=2,
            amenity_ids=amenity_ids if amenity_ids is not None else [self.pool.id],
        )

    def _matching_listing(
        self,
        *,
        category: str = PropertyCategory.RESIDENTIAL,
        city: str = "Athens",
        price: str = "240000.00",
        bedrooms: int | None = 2,
        amenities: list[Amenity] | None = None,
    ) -> Property:
        listing = self._property(
            title=f"Candidate {Property.objects.count()}",
            status=PropertyStatus.AVAILABLE,
            category=category,
            city=city,
            price=price,
            bedrooms=bedrooms,
        )
        listing.amenities.add(*(amenities if amenities is not None else [self.pool]))
        return listing

    def _property(
        self,
        *,
        title: str,
        status: str,
        category: str = PropertyCategory.RESIDENTIAL,
        city: str = "Athens",
        price: str = "250000.00",
        bedrooms: int | None = 2,
    ) -> Property:
        return Property.objects.create(
            title=title,
            status=status,
            category=category,
            city=city,
            area="Center",
            address_line=f"{city} address line",
            price=Decimal(price),
            bedrooms=bedrooms,
            listed_by=self.user,
        )
