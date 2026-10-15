# agentic-comm-automator/src/demo_email_tasks.py
"""
DEMO MODE (python main.py --demo)

Runs the whole workflow without a real mail server so the pipeline can be tested
without a Gmail App Password. Every "sent" email is:
  * saved as an .eml file in data/demo_outbox/ (open it with Outlook / Thunderbird / any mail app)
  * delivered to an in-memory inbox when it is addressed to the sender, so that
    process_inbox can find, parse and apply rules to it exactly like with IMAP.
"""
import os
import re

from email_tasks import EmailTasks
from utils import setup_logging, ensure_directory_exists

logger = setup_logging(__name__)


class DemoEmailTasks(EmailTasks):
    def __init__(self, sender_email, outbox_dir):
        super().__init__("demo-smtp", 0, "demo-imap", sender_email, "")
        self.outbox_dir = outbox_dir
        ensure_directory_exists(outbox_dir)
        self.inbox = []        # list of {"uid": bytes, "raw": bytes, "seen": bool}
        self._counter = 0
        logger.info(f"DEMO MODE: emails will be saved to '{outbox_dir}' instead of being sent.")

    def send_email(self, recipients, subject, body, attachments=None, is_html=False):
        msg, all_recipients = self.build_message(recipients, subject, body, attachments, is_html)
        if not all_recipients:
            logger.error("No recipients specified for email.")
            return False
        self._counter += 1
        safe = re.sub(r'[^A-Za-z0-9]+', '_', subject or "sms").strip('_')[:50] or "sms"
        path = os.path.join(self.outbox_dir, f"{self._counter:02d}_{safe}.eml")
        raw = msg.as_bytes()
        with open(path, "wb") as f:
            f.write(raw)
        if self.sender_email in all_recipients:   # mail to self -> lands in our demo inbox
            self.inbox.append({"uid": str(len(self.inbox) + 1).encode(), "raw": raw, "seen": False})
        logger.info(f"[DEMO] Email saved: {os.path.basename(path)} (to {len(all_recipients)} recipient(s))")
        return True

    def search_emails(self, mailbox='INBOX', criteria='UNSEEN', from_sender=None, subject_contains=None,
                      since_today=False):
        uids = []
        for item in self.inbox:
            info = self.parse_message(item["uid"], item["raw"])
            if criteria.upper() == 'UNSEEN' and item["seen"]:
                continue
            if from_sender and from_sender.lower() not in info["sender"].lower():
                continue
            if subject_contains and subject_contains.lower() not in info["subject"].lower():
                continue
            uids.append(item["uid"])
        logger.info(f"[DEMO] Found {len(uids)} email(s) in demo inbox.")
        return uids

    def fetch_email_content(self, uid, mark_as_read=True, download_attachments_dir=None):
        item = next((i for i in self.inbox if i["uid"] == uid), None)
        if item is None:
            return None
        info = self.parse_message(uid, item["raw"], download_attachments_dir)
        if mark_as_read:
            item["seen"] = True
            logger.info(f"[DEMO] Marked email UID {info['uid']} as read.")
        return info

    def close(self):
        pass
