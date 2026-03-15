import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseConnector

class EmailConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.server = config.get('server', 'imap.gmail.com')
        self.username = config['username']
        self.password = config['password']
        self.mail = None

    def connect(self) -> bool:
        try:
            self.mail = imaplib.IMAP4_SSL(self.server)
            self.mail.login(self.username, self.password)
            return True
        except Exception as e:
            print(f"Email connection failed: {e}")
            return False

    def fetch_data(self, since: datetime = None) -> List[Dict[str, Any]]:
        if not self.mail:
            return []

        try:
            self.mail.select('inbox')
            # Search for emails since date
            search_criteria = 'ALL'
            if since:
                search_criteria = f'SINCE {since.strftime("%d-%b-%Y")}'

            status, messages = self.mail.search(None, search_criteria)
            email_ids = messages[0].split()

            emails = []
            for email_id in email_ids[-50:]:  # Last 50 emails
                status, msg_data = self.mail.fetch(email_id, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)

                subject = self._decode_header(email_message['Subject'])
                sender = self._decode_header(email_message['From'])
                date = email_message['Date']

                # Get body
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = email_message.get_payload(decode=True).decode()

                emails.append({
                    'id': email_id.decode(),
                    'subject': subject,
                    'sender': sender,
                    'date': date,
                    'body': body,
                    'type': 'email'
                })

            return emails
        except Exception as e:
            print(f"Email fetch failed: {e}")
            return []

    def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        transformed = []
        for item in raw_data:
            transformed.append({
                'content': f"Subject: {item['subject']}\nFrom: {item['sender']}\nDate: {item['date']}\n\n{item['body']}",
                'source': 'email',
                'type': 'email',
                'metadata': {
                    'sender': item['sender'],
                    'subject': item['subject'],
                    'date': item['date']
                },
                'timestamp': datetime.now().isoformat()
            })
        return transformed

    def _decode_header(self, header):
        decoded, encoding = decode_header(header)[0]
        if isinstance(decoded, bytes):
            return decoded.decode(encoding or 'utf-8')
        return decoded

    def close(self):
        if self.mail:
            self.mail.logout()