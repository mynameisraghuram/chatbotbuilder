from django.urls import path
from core.public.views import (
    PublicPingView,
    PublicChatView,
    PublicLeadCaptureView,
    PublicLeadEmailOtpRequestView,
    PublicLeadEmailOtpConfirmView,
)

urlpatterns = [
    path("public/ping", PublicPingView.as_view(), name="public-ping"),
    path("public/chat", PublicChatView.as_view(), name="public-chat"),

    # A7.5 lead capture
    path("public/leads", PublicLeadCaptureView.as_view(), name="public-leads"),

    # OTP email verification
    path("public/leads/<uuid:lead_id>/verify-email/request", PublicLeadEmailOtpRequestView.as_view(), name="public-lead-otp-request"),
    path("public/leads/<uuid:lead_id>/verify-email/confirm", PublicLeadEmailOtpConfirmView.as_view(), name="public-lead-otp-confirm"),
]
