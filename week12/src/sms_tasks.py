# agentic-comm-automator/src/sms_tasks.py
from utils import setup_logging
from email_tasks import EmailTasks  # Reuse EmailTasks for sending the actual email

logger = setup_logging(__name__)


class SMSTasks:
    """
    Sends SMS via email-to-SMS gateways (number@gateway).
    A phone entry can be a plain number + carrier_name, or a full address such as
    '0812345678@your-gateway.com' (or any email address you want to use as an "SMS inbox").
    """
    def __init__(self, email_tasks_instance):
        if not isinstance(email_tasks_instance, EmailTasks):
            raise TypeError("SMSTasks requires an instance of EmailTasks.")
        self.email_tasks = email_tasks_instance

        # Common US carrier email-to-SMS gateways (some carriers have shut theirs down)
        self.carrier_gateways = {
            "att": "@txt.att.net",
            "verizon": "@vtext.com",
            "tmobile": "@tmomail.net",
            "sprint": "@messaging.sprintpcs.com",
            "boost": "@sms.boostmobile.com",
            "cricket": "@mms.cricketwireless.net",
            "us_cellular": "@email.uscc.net",
        }
        logger.info("SMSTasks initialized.")

    def _gateway_address(self, phone_number, carrier_name):
        phone_number = phone_number.strip()
        if '@' in phone_number:                       # already a full gateway / email address
            return phone_number
        if carrier_name and carrier_name.lower() in self.carrier_gateways:
            return f"{phone_number}{self.carrier_gateways[carrier_name.lower()]}"
        return None

    def send_sms(self, phone_numbers, message, carrier_name=None):
        """
        Sends `message` to every number. Returns True only if all of them were sent.
        """
        sent, attempted = 0, 0
        for phone_number in phone_numbers:
            attempted += 1
            address = self._gateway_address(phone_number, carrier_name)
            if not address:
                logger.warning(f"No gateway for '{phone_number}' (carrier '{carrier_name}'). "
                               "Use a full address like number@gateway or set a supported carrier.")
                continue
            # SMS gateways show the subject in front of the text, so keep it short
            if self.email_tasks.send_email({'to': [address]}, "SMS Alert", message[:300]):
                sent += 1
        logger.info(f"SMS: {sent}/{attempted} message(s) sent.")
        return attempted > 0 and sent == attempted
