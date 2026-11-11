from pydantic import BaseModel


class Ticket(BaseModel):
    id: str
    sender_email: str
    subject: str
    body: str
