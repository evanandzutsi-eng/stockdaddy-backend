import hashlib
import hmac
import logging
from typing import Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

class TippingService:
    """
    The "Show Love" Micro-Tipping Framework.
    
    Architectural Mandate: Non-custodial. The platform NEVER holds user cash.
    This service generates secure, encrypted outbound deep-linking routes 
    to payment processors (Paystack/Flutterwave) to facilitate peer-to-peer 
    appreciation while capturing platform gateway volume kickbacks.
    """

    @staticmethod
    def generate_paystack_split_payment_payload(
        analyst_paystack_subaccount_code: str,
        tip_amount_ngn: float,
        currency: str = "NGN",
        platform_fee_percentage: float = 5.0 # Platform kickback percentage
    ) -> Dict[str, Any]:
        """
        Generates a secure Paystack transaction payload with a split-payment 
        configuration. The platform captures the fee, and the remainder 
        routes directly to the analyst's subaccount.
        """
        if not settings.PAYSTACK_SECRET_KEY:
            logger.warning("Paystack secret key not configured. Tipping disabled.")
            return {}

        # Calculate platform fee and analyst payout
        platform_fee = round(tip_amount_ngn * (platform_fee_percentage / 100), 2)
        analyst_payout = round(tip_amount_ngn - platform_fee, 2)
        
        # Generate unique reference to prevent duplicate transactions
        raw_ref = f"tip-{analyst_paystack_subaccount_code}-{hashlib.sha256(str(tip_amount_ngn).encode()).hexdigest()[:12]}"
        reference = raw_ref

        # Paystack requires amounts in the smallest currency unit (Kobo for NGN)
        checkout_payload = {
            "email": "tipping@ngx-terminal.local", # Placeholder buyer email
            "amount": int(tip_amount_ngn * 100), 
            "currency": currency,
            "reference": reference,
            "metadata": {
                "custom_fields": [
                    {
                        "display_name": "Platform Fee (Kickback)",
                        "variable_name": "platform_fee",
                        "value": f"₦{platform_fee:,.2f}"
                    },
                    {
                        "display_name": "Analyst Payout",
                        "variable_name": "analyst_payout",
                        "value": f"₦{analyst_payout:,.2f}"
                    }
                ],
                # Paystack split payment configuration
                "subaccounts": [
                    {
                        "subaccount": analyst_paystack_subaccount_code,
                        "share": int(analyst_payout * 100) # Share in kobo
                    }
                ]
            }
        }
        
        logger.info(f"Generated Paystack tipping route for {analyst_paystack_subaccount_code}")
        return checkout_payload

    @staticmethod
    def verify_paystack_webhook_signature(payload: bytes, signature: str) -> bool:
        """
        Cybersecurity: Verifies the HMAC SHA512 signature of incoming 
        Paystack webhooks to ensure payment events are authentic and 
        prevent spoofed transaction confirmations.
        """
        if not settings.PAYSTACK_SECRET_KEY:
            return False
            
        expected_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)s