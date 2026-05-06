from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from homefinder.apps.interactions.models import (
    BookingRequest,
    Payment,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
)
from homefinder.apps.interactions.services import (
    SimulatedPaymentService,
    complete_simulated_payment,
    create_booking_fee_payment,
    create_simulated_payment,
)
from homefinder.apps.properties.models import Property, PropertyCategory
from homefinder.apps.users.models import User


class SimulatedPaymentFlowTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="renter@example.com",
            password="password123",
            full_name="Renter Example",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="password123",
            full_name="Other Example",
        )
        self.rental_property = Property.objects.create(
            title="Payment Rental",
            description="Payment Rental description",
            category=PropertyCategory.RENTAL,
            city="Athens",
            area="Center",
            price=Decimal("1200.00"),
        )
        self.booking_request = BookingRequest.objects.create(
            user=self.user,
            property=self.rental_property,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
        )
        self.service = SimulatedPaymentService()

    def test_valid_booking_fee_payment_persists_as_pending(self) -> None:
        payment = self.service.create_booking_fee_payment(
            booking_request=self.booking_request,
            amount=Decimal("49.99"),
            method=PaymentMethod.CREDIT_CARD,
        )

        payment.refresh_from_db()
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.booking_request, self.booking_request)
        self.assertEqual(payment.amount, Decimal("49.99"))
        self.assertEqual(payment.payment_method, PaymentMethod.CREDIT_CARD)
        self.assertEqual(payment.payment_purpose, PaymentPurpose.BOOKING_FEE)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_premium_simulated_payment_can_persist_without_booking(self) -> None:
        payment = self.service.create_payment(
            user=self.user,
            amount="19.00",
            method=PaymentMethod.BANK_TRANSFER,
            purpose=PaymentPurpose.PREMIUM_SERVICE,
        )

        self.assertIsNone(payment.booking_request)
        self.assertEqual(payment.payment_purpose, PaymentPurpose.PREMIUM_SERVICE)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_non_booking_payment_can_persist_without_booking_at_database_level(self) -> None:
        Payment.objects.bulk_create(
            [
                Payment(
                    user=self.user,
                    payment_purpose=PaymentPurpose.PREMIUM_SERVICE,
                    payment_method=PaymentMethod.BANK_TRANSFER,
                    amount=Decimal("19.00"),
                )
            ]
        )

        payment = Payment.objects.get()
        self.assertIsNone(payment.booking_request)
        self.assertEqual(payment.payment_purpose, PaymentPurpose.PREMIUM_SERVICE)

    def test_required_payment_fields_are_enforced_by_model_validation(self) -> None:
        payment = Payment(
            user=self.user,
            booking_request=self.booking_request,
            payment_purpose=PaymentPurpose.BOOKING_FEE,
            payment_method="",
            amount=None,
        )

        with self.assertRaises(ValidationError) as raised:
            payment.full_clean()

        self.assertIn("payment_method", raised.exception.message_dict)
        self.assertIn("amount", raised.exception.message_dict)

    def test_required_payment_fields_are_enforced_by_database(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.bulk_create(
                    [
                        Payment(
                            user=self.user,
                            booking_request=self.booking_request,
                            payment_purpose=PaymentPurpose.BOOKING_FEE,
                            payment_method=None,
                            amount=Decimal("49.99"),
                        )
                    ]
                )
        self.assertEqual(Payment.objects.count(), 0)

    def test_valid_status_transitions_succeed(self) -> None:
        payment = self._create_pending_payment()

        completed_payment = self.service.complete_payment(payment)

        completed_payment.refresh_from_db()
        self.assertEqual(completed_payment.status, PaymentStatus.COMPLETED)

    def test_invalid_status_transition_is_rejected(self) -> None:
        payment = self._create_pending_payment()
        self.service.complete_payment(payment)

        with self.assertRaises(ValidationError) as raised:
            self.service.fail_payment(payment)

        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.COMPLETED)
        self.assertIn("status", raised.exception.message_dict)

    def test_failed_payment_is_terminal(self) -> None:
        payment = self._create_pending_payment()
        self.service.fail_payment(payment)

        with self.assertRaises(ValidationError):
            self.service.complete_payment(payment)

        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.FAILED)

    def test_duplicate_transition_is_idempotent(self) -> None:
        payment = self._create_pending_payment()
        completed_payment = self.service.complete_payment(payment)
        first_updated_at = completed_payment.updated_at

        duplicate_payment = self.service.complete_payment(payment)

        duplicate_payment.refresh_from_db()
        self.assertEqual(duplicate_payment.status, PaymentStatus.COMPLETED)
        self.assertEqual(duplicate_payment.updated_at, first_updated_at)

    def test_invalid_status_value_is_rejected(self) -> None:
        payment = self._create_pending_payment()

        with self.assertRaises(ValidationError) as raised:
            self.service.transition_payment_status(payment, status="NOT_A_STATUS")

        self.assertIn("status", raised.exception.message_dict)

    def test_invalid_method_and_purpose_values_are_rejected(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            self.service.create_payment(
                user=self.user,
                amount="19.00",
                method="REAL_GATEWAY_CARD",
                purpose="REAL_GATEWAY_PURPOSE",
            )

        self.assertIn("payment_method", raised.exception.message_dict)
        self.assertIn("payment_purpose", raised.exception.message_dict)
        self.assertEqual(Payment.objects.count(), 0)

    def test_invalid_amount_values_are_rejected(self) -> None:
        invalid_amounts = ("0.00", "-1.00", "not-money")

        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                with self.assertRaises(ValidationError) as raised:
                    self.service.create_payment(
                        user=self.user,
                        amount=amount,
                        method=PaymentMethod.CREDIT_CARD,
                        purpose=PaymentPurpose.PREMIUM_SERVICE,
                    )

                self.assertIn("amount", raised.exception.message_dict)

        self.assertEqual(Payment.objects.count(), 0)

    def test_booking_fee_requires_booking_link(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            self.service.create_payment(
                user=self.user,
                amount="49.99",
                method=PaymentMethod.CREDIT_CARD,
                purpose=PaymentPurpose.BOOKING_FEE,
            )

        self.assertIn("booking_request", raised.exception.message_dict)
        self.assertEqual(Payment.objects.count(), 0)

    def test_booking_fee_without_booking_cannot_persist_at_database_level(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.bulk_create(
                    [
                        Payment(
                            user=self.user,
                            payment_purpose=PaymentPurpose.BOOKING_FEE,
                            payment_method=PaymentMethod.CREDIT_CARD,
                            amount=Decimal("49.99"),
                        )
                    ]
                )

        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_user_must_match_linked_booking_requester(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            self.service.create_payment(
                user=self.other_user,
                booking_request=self.booking_request,
                amount="49.99",
                method=PaymentMethod.CREDIT_CARD,
                purpose=PaymentPurpose.BOOKING_FEE,
            )

        self.assertIn("booking_request", raised.exception.message_dict)
        self.assertEqual(Payment.objects.count(), 0)

    def test_mismatched_booking_user_cannot_persist_through_model_save(self) -> None:
        payment = Payment(
            user=self.other_user,
            booking_request=self.booking_request,
            payment_purpose=PaymentPurpose.BOOKING_FEE,
            payment_method=PaymentMethod.CREDIT_CARD,
            amount=Decimal("49.99"),
        )

        with self.assertRaises(ValidationError) as raised:
            payment.save()

        self.assertIn("booking_request", raised.exception.message_dict)
        self.assertEqual(Payment.objects.count(), 0)

    def test_mismatched_booking_user_cannot_persist_through_bulk_create(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            Payment.objects.bulk_create(
                [
                    Payment(
                        user=self.other_user,
                        booking_request=self.booking_request,
                        payment_purpose=PaymentPurpose.BOOKING_FEE,
                        payment_method=PaymentMethod.CREDIT_CARD,
                        amount=Decimal("49.99"),
                    )
                ]
            )

        self.assertIn("booking_request", raised.exception.message_dict)
        self.assertEqual(Payment.objects.count(), 0)

    def test_invalid_booking_reference_is_rejected_by_database(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.bulk_create(
                    [
                        Payment(
                            user=self.user,
                            booking_request_id=999999,
                            payment_purpose=PaymentPurpose.BOOKING_FEE,
                            payment_method=PaymentMethod.CREDIT_CARD,
                            amount=Decimal("49.99"),
                        )
                    ]
                )
                connection.check_constraints()

        self.assertEqual(Payment.objects.count(), 0)

    def test_booking_deletion_is_blocked_when_payment_exists(self) -> None:
        payment = self._create_pending_payment()

        with self.assertRaises(ProtectedError):
            self.booking_request.delete()

        payment.refresh_from_db()
        self.assertEqual(payment.booking_request, self.booking_request)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_payment_remains_transitionable_after_blocked_booking_deletion(self) -> None:
        payment = self._create_pending_payment()

        with self.assertRaises(ProtectedError):
            self.booking_request.delete()

        completed_payment = self.service.complete_payment(payment)

        completed_payment.refresh_from_db()
        self.assertEqual(completed_payment.status, PaymentStatus.COMPLETED)
        self.assertEqual(completed_payment.booking_request, self.booking_request)

    def test_direct_invalid_status_cannot_persist(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.bulk_create(
                    [
                        Payment(
                            user=self.user,
                            booking_request=self.booking_request,
                            payment_purpose=PaymentPurpose.BOOKING_FEE,
                            payment_method=PaymentMethod.CREDIT_CARD,
                            amount=Decimal("49.99"),
                            status="NOT_A_STATUS",
                        )
                    ]
                )

        self.assertEqual(Payment.objects.count(), 0)

    def test_direct_non_positive_amount_cannot_persist(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.bulk_create(
                    [
                        Payment(
                            user=self.user,
                            booking_request=self.booking_request,
                            payment_purpose=PaymentPurpose.BOOKING_FEE,
                            payment_method=PaymentMethod.CREDIT_CARD,
                            amount=Decimal("0.00"),
                        )
                    ]
                )

        self.assertEqual(Payment.objects.count(), 0)

    def test_completing_payment_through_public_helper_updates_status(self) -> None:
        payment = create_booking_fee_payment(
            booking_request=self.booking_request,
            amount="49.99",
            method=PaymentMethod.CREDIT_CARD,
        )

        completed_payment = complete_simulated_payment(payment)

        completed_payment.refresh_from_db()
        self.assertEqual(completed_payment.status, PaymentStatus.COMPLETED)

    def test_competing_stale_transitions_allow_only_one_terminal_outcome(self) -> None:
        payment = self._create_pending_payment()
        stale_complete = Payment.objects.get(pk=payment.pk)
        stale_fail = Payment.objects.get(pk=payment.pk)

        completed_payment = self.service.complete_payment(stale_complete)

        with self.assertRaises(ValidationError) as raised:
            self.service.fail_payment(stale_fail)

        payment.refresh_from_db()
        self.assertEqual(completed_payment.status, PaymentStatus.COMPLETED)
        self.assertEqual(payment.status, PaymentStatus.COMPLETED)
        self.assertIn("status", raised.exception.message_dict)
        self.assertFalse(Payment.objects.filter(pk=payment.pk, status=PaymentStatus.FAILED).exists())

    def test_unsaved_payment_object_is_rejected_by_transition_service(self) -> None:
        payment = Payment(
            user=self.user,
            booking_request=self.booking_request,
            payment_purpose=PaymentPurpose.BOOKING_FEE,
            payment_method=PaymentMethod.CREDIT_CARD,
            amount=Decimal("49.99"),
        )

        with self.assertRaises(ValidationError) as raised:
            self.service.complete_payment(payment)

        self.assertIn("payment", raised.exception.message_dict)

    def test_non_payment_object_is_rejected_by_transition_service(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            self.service.transition_payment_status(object(), status=PaymentStatus.COMPLETED)

        self.assertIn("payment", raised.exception.message_dict)

    def test_simulated_payment_flow_makes_no_external_delivery_calls(self) -> None:
        with patch("homefinder.apps.interactions.services.send_mail") as send_mail:
            payment = create_simulated_payment(
                user=self.user,
                booking_request=self.booking_request,
                amount="49.99",
                method=PaymentMethod.CREDIT_CARD,
                purpose=PaymentPurpose.BOOKING_FEE,
            )
            complete_simulated_payment(payment)

        send_mail.assert_not_called()

    def _create_pending_payment(self) -> Payment:
        return self.service.create_booking_fee_payment(
            booking_request=self.booking_request,
            amount="49.99",
            method=PaymentMethod.CREDIT_CARD,
        )
