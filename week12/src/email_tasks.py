# agentic-comm-automator/src/email_tasks.py
import os
import smtplib
import imaplib
import email
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.header import decode_header
from email.utils import parseaddr, formatdate, make_msgid

from utils import setup_logging, ensure_directory_exists

logger = setup_logging(__name__)


class EmailTasks:
    """
    Handles sending (SMTP) and receiving (IMAP) emails.
    Building and parsing messages are separate methods so they can be reused by DemoEmailTasks.
    """
    def __init__(self, smtp_server, smtp_port, imap_server, sender_email, sender_password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.imap_server = imap_server
        self.sender_email = sender_email
        self.sender_password = sender_password
        self._smtp = None
        self._imap = None
        logger.info("EmailTasks initialized.")

    # ------------------------------------------------------------------ building / parsing
    def build_message(self, recipients, subject, body, attachments=None, is_html=False):
        """Builds a MIME message. Returns (message, list_of_all_recipient_addresses)."""
        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid()

        to_list = recipients.get('to', [])
        cc_list = recipients.get('cc', [])
        bcc_list = recipients.get('bcc', [])  # BCC is not written to the headers
        msg['To'] = ", ".join(to_list)
        if cc_list:
            msg['Cc'] = ", ".join(cc_list)

        msg.attach(MIMEText(body, 'html' if is_html else 'plain', 'utf-8'))

        for attachment_path in attachments or []:
            if not os.path.exists(attachment_path):
                logger.warning(f"Attachment file not found: {attachment_path}. Skipping.")
                continue
            try:
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)
                logger.info(f"Attached file: {os.path.basename(attachment_path)}")
            except Exception as e:
                logger.error(f"Error attaching file {attachment_path}: {e}")

        # remove duplicates (e.g. sender in both To and Cc) but keep order
        all_recipients = list(dict.fromkeys(to_list + cc_list + bcc_list))
        return msg, all_recipients

    def parse_message(self, uid, raw_email, download_attachments_dir=None):
        """Parses raw RFC822 bytes into a dict; optionally saves attachments."""
        msg = email.message_from_bytes(raw_email)
        sender_header = self._decode_header_part(msg['From'])
        sender_address = parseaddr(sender_header)[1] or sender_header
        subject = self._decode_header_part(msg['Subject'])

        text_body, html_body, attachments_meta = "", "", []
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            filename = part.get_filename()
            if filename:
                filename = self._decode_header_part(filename)

            if "attachment" in disposition or filename:
                filepath = None
                if filename and download_attachments_dir:
                    ensure_directory_exists(download_attachments_dir)
                    filepath = os.path.join(download_attachments_dir, os.path.basename(filename))
                    try:
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        logger.info(f"Downloaded attachment: {filepath}")
                    except Exception as e:
                        logger.error(f"Error downloading attachment {filename}: {e}")
                        filepath = None
                attachments_meta.append({'filename': filename, 'filepath': filepath})
            elif content_type in ("text/plain", "text/html"):
                try:
                    text = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                except Exception as e:
                    logger.warning(f"Could not decode {content_type} part of email {uid}: {e}")
                    continue
                if content_type == "text/plain":
                    text_body += text
                else:
                    html_body += text

        return {
            "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
            "sender": sender_address,
            "subject": subject,
            "text_body": text_body,
            "html_body": html_body,
            "has_attachments": bool(attachments_meta),
            "attachments_meta": attachments_meta,
        }

    # ------------------------------------------------------------------ SMTP
    def _connect_smtp(self):
        if self._smtp:
            return True
        try:
            self._smtp = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            self._smtp.starttls()
            self._smtp.login(self.sender_email, self.sender_password)
            logger.info("Connected and logged into SMTP server.")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed. Check email and APP PASSWORD. Error: {e}")
        except Exception as e:
            logger.error(f"SMTP connect/login failed: {e}")
        self._smtp = None
        return False

    def _disconnect_smtp(self):
        if self._smtp:
            try:
                self._smtp.quit()
            except Exception as e:
                logger.warning(f"Error during SMTP disconnection: {e}")
            finally:
                self._smtp = None

    def send_email(self, recipients, subject, body, attachments=None, is_html=False):
        """
        Sends an email. `recipients` = {'to': [...], 'cc': [...], 'bcc': [...]}.
        Returns True on success.
        """
        msg, all_recipients = self.build_message(recipients, subject, body, attachments, is_html)
        if not all_recipients:
            logger.error("No recipients specified for email.")
            return False
        if not self._connect_smtp():
            return False
        try:
            self._smtp.send_message(msg, from_addr=self.sender_email, to_addrs=all_recipients)
            logger.info(f"Email sent to {len(all_recipients)} recipient(s). Subject: '{subject}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
        finally:
            self._disconnect_smtp()

    # ------------------------------------------------------------------ IMAP
    def _connect_imap(self, mailbox='INBOX'):
        if self._imap:
            return True
        try:
            self._imap = imaplib.IMAP4_SSL(self.imap_server)
            self._imap.login(self.sender_email, self.sender_password)
            self._imap.select(mailbox)
            logger.info("Connected and logged into IMAP server.")
            return True
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP authentication failed. Check email and APP PASSWORD (and that IMAP is enabled). Error: {e}")
        except Exception as e:
            logger.error(f"IMAP connect/login failed: {e}")
        self._imap = None
        return False

    def close(self):
        """Closes the IMAP connection (kept open between search and fetch)."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception as e:
                logger.warning(f"Error during IMAP disconnection: {e}")
            finally:
                self._imap = None

    def search_emails(self, mailbox='INBOX', criteria='UNSEEN', from_sender=None, subject_contains=None,
                      since_today=False):
        """
        Searches emails and returns a list of UIDs (bytes), or None if the mailbox could not be reached.
        Uses UID SEARCH so the ids stay valid for the following UID FETCH / STORE.
        """
        if not self._connect_imap(mailbox):
            return None
        try:
            self._imap.select(mailbox)
            query = [criteria]
            if from_sender:
                query += ['FROM', f'"{from_sender}"']
            if subject_contains:
                query += ['SUBJECT', f'"{subject_contains}"']
            if since_today:
                query += ['SINCE', datetime.date.today().strftime("%d-%b-%Y")]
            status, data = self._imap.uid('search', None, *query)
            if status != 'OK':
                logger.error(f"IMAP search failed. Status: {status}")
                return None
            uids = data[0].split()
            logger.info(f"Found {len(uids)} email(s) matching {' '.join(query)} in '{mailbox}'.")
            return uids
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return None

    def fetch_email_content(self, uid, mark_as_read=True, download_attachments_dir=None):
        """Fetches one email by UID, optionally marks it as read and downloads attachments."""
        if not self._connect_imap():
            return None
        try:
            status, msg_data = self._imap.uid('fetch', uid, '(BODY.PEEK[])')
            if status != 'OK' or not msg_data or msg_data[0] is None:
                logger.error(f"Failed to fetch email UID {uid}. Status: {status}")
                return None
            info = self.parse_message(uid, msg_data[0][1], download_attachments_dir)
            if mark_as_read:
                self._imap.uid('store', uid, '+FLAGS', '(\\Seen)')
                logger.info(f"Marked email UID {info['uid']} as read.")
            return info
        except Exception as e:
            logger.error(f"Error fetching/parsing email UID {uid}: {e}")
            return None

    @staticmethod
    def _decode_header_part(header_value):
        """Decodes encoded headers such as '=?UTF-8?B?...?='."""
        if header_value is None:
            return ""
        decoded = ""
        for part, charset in decode_header(header_value):
            if isinstance(part, bytes):
                try:
                    decoded += part.decode(charset or 'utf-8')
                except (LookupError, UnicodeDecodeError):
                    decoded += part.decode('latin-1', errors='replace')
            else:
                decoded += part
        return decoded.strip()
